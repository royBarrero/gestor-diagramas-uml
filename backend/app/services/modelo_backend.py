"""CU11: transforma el contenido de un diagrama de clases en un modelo
estructural intermedio (entidades, campos, relaciones, endpoints) — la
misma representación que hoy consume el generador de código Java
(`generacion_backend.py`) y que CU12 (generación de frontend Flutter "a
partir del backend generado") va a poder reutilizar directamente en vez de
tener que parsear el .zip generado. Mantener este archivo como la única
fuente de verdad sobre cómo el diagrama se traduce a entidades/relaciones.

Convenciones de relación (mismas ya documentadas y probadas en
`xmi_diagrama.py` para XMI/UML2):
- Herencia: `source` es la subclase, `target` la superclase.
- Agregación/Composición: `source` es el "todo", `target` la "parte".
- La multiplicidad mostrada cerca de un extremo describe cuántas instancias
  de esa clase participan por cada instancia del otro extremo (ej. "Persona
  1 -- * Pedido": una Persona tiene muchos Pedidos, cada Pedido tiene una
  Persona).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from app.services.exportacion_diagrama import validar_contenido

TIPOS_DATO_A_JAVA = {
    "string": "String",
    "int": "int",
    "long": "long",
    "double": "double",
    "float": "float",
    "boolean": "boolean",
    "char": "char",
    "date": "LocalDate",
    "list": "List<String>",
}

_PATRON_MULTIPLICIDAD = re.compile(r"^\s*(\d+|\*)\s*(?:\.\.\s*(\d+|\*)\s*)?$")


class GeneracionInvalidaError(Exception):
    """El diagrama no tiene clases, o tiene algo que impide generar código
    coherente (ej. dos clases que sanitizan al mismo nombre Java)."""


def _quitar_diacriticos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def _a_identificador(texto: str | None, mayuscula_inicial: bool, respaldo: str) -> str:
    limpio = _quitar_diacriticos(texto or "")
    partes = [p for p in re.split(r"[^a-zA-Z0-9]+", limpio) if p]
    if not partes:
        return respaldo if mayuscula_inicial else respaldo[0].lower() + respaldo[1:]

    resultado = "".join(p[:1].upper() + p[1:] for p in partes)
    if not mayuscula_inicial:
        resultado = resultado[:1].lower() + resultado[1:]
    if resultado[0].isdigit():
        resultado = (respaldo if mayuscula_inicial else "campo") + resultado
    return resultado


def _pluralizar(palabra: str) -> str:
    return palabra if palabra.endswith("s") else f"{palabra}s"


def _endpoint_de(nombre_java: str) -> str:
    kebab = re.sub(r"(?<!^)(?=[A-Z])", "-", nombre_java).lower()
    return _pluralizar(kebab)


def _es_coleccion(multiplicidad: str | None) -> bool:
    if not multiplicidad:
        return False
    match = _PATRON_MULTIPLICIDAD.match(multiplicidad)
    if match:
        limite_superior = match.group(2) or match.group(1)
        if limite_superior == "*":
            return True
        try:
            return int(limite_superior) > 1
        except ValueError:
            return False
    return "*" in multiplicidad


@dataclass
class CampoModelo:
    nombre: str
    tipo_java: str
    es_lista: bool = False


@dataclass
class RelacionModelo:
    tipo: str  # "oneToOne" | "manyToOne" | "oneToMany" | "manyToMany"
    nombre: str
    entidad_relacionada: str  # nombre_java de la entidad del otro lado
    es_coleccion: bool
    propietaria: bool  # True: esta entidad tiene la FK (@JoinColumn) o la @JoinTable
    mapped_by: str | None = None  # nombre del campo del otro lado, si esta es la inversa
    cascade: str | None = None
    orphan_removal: bool = False


@dataclass
class MetodoModelo:
    nombre: str


@dataclass
class EntidadModelo:
    nombre_original: str
    nombre_java: str
    campo_id_nombre: str
    campo_id_tipo: str
    campo_id_generado: bool  # False si el usuario ya definía un atributo "id"
    campos: list[CampoModelo] = field(default_factory=list)
    metodos: list[MetodoModelo] = field(default_factory=list)
    extiende: str | None = None  # nombre_java de la superclase
    tiene_subclases: bool = False
    relaciones: list[RelacionModelo] = field(default_factory=list)
    endpoint: str = ""

    def nombres_ocupados(self) -> set[str]:
        ocupados = {self.campo_id_nombre}
        ocupados.update(c.nombre for c in self.campos)
        ocupados.update(r.nombre for r in self.relaciones)
        return ocupados


@dataclass
class ModeloBackend:
    paquete: str
    entidades: list[EntidadModelo]


def campos_heredados(entidad: EntidadModelo, entidades_por_nombre: dict[str, EntidadModelo]) -> list[CampoModelo]:
    """Atributos propios de las superclases (no de relaciones), recorriendo
    toda la cadena de herencia hacia arriba. No incluye los atributos
    propios de `entidad` (ver `entidad.campos`). Compartido entre CU11
    (`generacion_backend.py`, DTOs que `extends` la superclase) y CU12
    (`generacion_frontend.py`, modelo Dart plano vía `todos_los_campos`)."""
    heredados: list[CampoModelo] = []
    nombre_superclase = entidad.extiende
    while nombre_superclase:
        superclase = entidades_por_nombre[nombre_superclase]
        heredados = list(superclase.campos) + heredados
        nombre_superclase = superclase.extiende
    return heredados


def todos_los_campos(entidad: EntidadModelo, entidades_por_nombre: dict[str, EntidadModelo]) -> list[CampoModelo]:
    """`campos_heredados` + los propios de `entidad`, en ese orden (de la
    superclase más alejada hacia la propia clase) — la lista "aplanada"
    completa, para generadores que no necesitan distinguir origen (ej. un
    modelo Dart plano, sin herencia)."""
    return campos_heredados(entidad, entidades_por_nombre) + entidad.campos


def _tipo_java_de(tipo_dato: str | None) -> tuple[str, bool]:
    clave = (tipo_dato or "").strip().lower()
    tipo = TIPOS_DATO_A_JAVA.get(clave, tipo_dato if tipo_dato else "String")
    return tipo, tipo == "List<String>"


def _nombre_unico(entidad: EntidadModelo, propuesto: str) -> str:
    if propuesto not in entidad.nombres_ocupados():
        return propuesto
    contador = 2
    while f"{propuesto}{contador}" in entidad.nombres_ocupados():
        contador += 1
    return f"{propuesto}{contador}"


def _construir_entidad(node: dict) -> EntidadModelo:
    nombre_original = node["data"]["nombre"]
    nombre_java = _a_identificador(nombre_original, mayuscula_inicial=True, respaldo="Clase")

    atributo_id = next(
        (a for a in node["data"]["atributos"] if _quitar_diacriticos(a["texto"]).strip().lower() == "id"),
        None,
    )
    if atributo_id is not None:
        tipo_id, _ = _tipo_java_de(atributo_id["tipo"])
        campo_id_nombre, campo_id_tipo, campo_id_generado = "id", tipo_id, False
    else:
        campo_id_nombre, campo_id_tipo, campo_id_generado = "id", "Long", True

    campos = []
    for atributo in node["data"]["atributos"]:
        if atributo is atributo_id:
            continue
        nombre_campo = _a_identificador(atributo["texto"], mayuscula_inicial=False, respaldo="campo")
        tipo_java, es_lista = _tipo_java_de(atributo["tipo"])
        campos.append(CampoModelo(nombre=nombre_campo, tipo_java=tipo_java, es_lista=es_lista))

    metodos = [
        MetodoModelo(nombre=_a_identificador(metodo["texto"], mayuscula_inicial=False, respaldo="metodo"))
        for metodo in node["data"]["metodos"]
    ]

    return EntidadModelo(
        nombre_original=nombre_original,
        nombre_java=nombre_java,
        campo_id_nombre=campo_id_nombre,
        campo_id_tipo=campo_id_tipo,
        campo_id_generado=campo_id_generado,
        campos=campos,
        metodos=metodos,
        endpoint=_endpoint_de(nombre_java),
    )


def _procesar_herencia(edge: dict, entidades_por_id: dict[str, EntidadModelo]) -> None:
    subclase = entidades_por_id[edge["source"]]
    superclase = entidades_por_id[edge["target"]]
    subclase.extiende = superclase.nombre_java
    superclase.tiene_subclases = True
    # La subclase hereda el id de la raíz; no debe redeclararlo.
    subclase.campo_id_nombre = superclase.campo_id_nombre
    subclase.campo_id_tipo = superclase.campo_id_tipo
    subclase.campo_id_generado = False


def _procesar_relacion_asociativa(edge: dict, entidades_por_id: dict[str, EntidadModelo]) -> None:
    data = edge["data"]
    tipo = data["tipo"]
    origen = entidades_por_id[edge["source"]]
    destino = entidades_por_id[edge["target"]]

    col_origen = _es_coleccion(data.get("multiplicidadOrigen"))
    col_destino = _es_coleccion(data.get("multiplicidadDestino"))

    nombre_relacion = data.get("nombre")
    nombre_base = _a_identificador(nombre_relacion, mayuscula_inicial=False, respaldo="") if nombre_relacion else None

    nombre_en_origen = nombre_base or _a_identificador(destino.nombre_java, mayuscula_inicial=False, respaldo="relacion")
    nombre_en_destino = nombre_base or _a_identificador(origen.nombre_java, mayuscula_inicial=False, respaldo="relacion")

    if col_origen and col_destino:
        nombre_en_origen = _pluralizar(nombre_en_origen)
        nombre_en_destino = _pluralizar(nombre_en_destino)
        rel_origen = RelacionModelo("manyToMany", nombre_en_origen, destino.nombre_java, True, propietaria=True)
        rel_destino = RelacionModelo(
            "manyToMany", nombre_en_destino, origen.nombre_java, True, propietaria=False, mapped_by=nombre_en_origen
        )
    elif col_origen and not col_destino:
        # origen es el lado "muchos": tiene la FK (referencia simple a destino).
        rel_origen = RelacionModelo("manyToOne", nombre_en_origen, destino.nombre_java, False, propietaria=True)
        nombre_en_destino = _pluralizar(nombre_en_destino)
        rel_destino = RelacionModelo(
            "oneToMany", nombre_en_destino, origen.nombre_java, True, propietaria=False, mapped_by=nombre_en_origen
        )
    elif col_destino and not col_origen:
        # destino es el lado "muchos": tiene la FK (referencia simple a origen).
        nombre_en_origen = _pluralizar(nombre_en_origen)
        rel_origen = RelacionModelo(
            "oneToMany", nombre_en_origen, destino.nombre_java, True, propietaria=False, mapped_by=nombre_en_destino
        )
        rel_destino = RelacionModelo("manyToOne", nombre_en_destino, origen.nombre_java, False, propietaria=True)
    else:
        rel_origen = RelacionModelo("oneToOne", nombre_en_origen, destino.nombre_java, False, propietaria=True)
        rel_destino = RelacionModelo(
            "oneToOne", nombre_en_destino, origen.nombre_java, False, propietaria=False, mapped_by=nombre_en_origen
        )

    # Convención: origen = "todo" en agregación/composición -> el cascade
    # de ciclo de vida se declara sobre el campo que tiene origen.
    if tipo == "composicion":
        rel_origen.cascade = "CascadeType.ALL"
        rel_origen.orphan_removal = True
    elif tipo == "agregacion":
        rel_origen.cascade = "CascadeType.PERSIST, CascadeType.MERGE"

    rel_origen.nombre = _nombre_unico(origen, rel_origen.nombre)
    rel_destino.nombre = _nombre_unico(destino, rel_destino.nombre)

    origen.relaciones.append(rel_origen)
    destino.relaciones.append(rel_destino)


def construir_modelo_backend(contenido: dict, nombre_proyecto: str) -> ModeloBackend:
    contenido = validar_contenido(contenido)
    nodes, edges = contenido["nodes"], contenido["edges"]

    if not nodes:
        raise GeneracionInvalidaError("El diagrama no tiene ninguna clase definida.")

    entidades_por_id = {node["id"]: _construir_entidad(node) for node in nodes}

    nombres_vistos: dict[str, str] = {}
    for entidad in entidades_por_id.values():
        if entidad.nombre_java in nombres_vistos:
            otra = nombres_vistos[entidad.nombre_java]
            raise GeneracionInvalidaError(
                f'Las clases "{otra}" y "{entidad.nombre_original}" generan el mismo nombre de clase Java '
                f'("{entidad.nombre_java}"); renombrá una para poder generar el backend.'
            )
        nombres_vistos[entidad.nombre_java] = entidad.nombre_original

    for edge in edges:
        if edge["data"]["tipo"] == "herencia":
            _procesar_herencia(edge, entidades_por_id)

    for edge in edges:
        tipo = edge["data"]["tipo"]
        if tipo in ("asociacion", "agregacion", "composicion"):
            _procesar_relacion_asociativa(edge, entidades_por_id)
        # "dependencia" no genera ningún elemento de código: es una relación
        # de uso/documentación, no de persistencia.

    paquete = "com.generado." + (_a_identificador(nombre_proyecto, mayuscula_inicial=False, respaldo="proyecto").lower() or "proyecto")
    paquete = re.sub(r"[^a-z0-9.]", "", paquete) or "com.generado.proyecto"

    return ModeloBackend(paquete=paquete, entidades=list(entidades_por_id.values()))
