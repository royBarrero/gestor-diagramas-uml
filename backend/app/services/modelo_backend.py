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
- Clase de asociación (`data.claseAsociacion` de una asociación): la clase
  intermedia X se vuelve dueña de dos `manyToOne` (hacia cada extremo) y los
  extremos la ven como `oneToMany`; no se genera la relación directa entre
  los extremos, sea cual sea su multiplicidad.

Tipo de clase (`data.tipoClase`):
- "clase" y "abstracta" son entidades JPA (`entidades`); la abstracta no se
  puede instanciar, así que el generador no le da alta ni datos de ejemplo.
- "enumeracion" es un `enum` Java (`enumeraciones`): sus atributos son los
  literales, y un atributo de otra clase cuyo tipo es la enumeración se
  persiste con `@Enumerated`.
- "interfaz" es una `interface` Java (`interfaces`). Realización:
  `source` implementa a `target`. Ni interfaces ni enumeraciones son tablas,
  así que una asociación hacia ellas no se genera (queda en `advertencias`).
- Un atributo estático no es columna (va a `campos_estaticos`); un método
  estático va en la entidad, no como stub del Service.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from app.services.constantes_diagrama import PATRON_MULTIPLICIDAD, TIPOS_DATO_A_JAVA, normalizar, parsear_firma
from app.services.exportacion_diagrama import validar_contenido

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
    """Plural en español de la última palabra (camelCase o kebab-case solo
    importan por cómo terminan). Ya llega sin tildes. Terminada en s/x se
    deja igual: o ya está en plural o es invariable (lunes, tesis)."""
    if not palabra:
        return palabra
    final = palabra[-1].lower()
    if final in "sx":
        return palabra
    if final == "z":
        return f"{palabra[:-1]}ces"
    if final in "lnrdjy":
        return f"{palabra}es"
    return f"{palabra}s"


def _endpoint_de(nombre_java: str) -> str:
    kebab = re.sub(r"(?<!^)(?=[A-Z])", "-", nombre_java).lower()
    return _pluralizar(kebab)


def _es_coleccion(multiplicidad: str | None) -> bool:
    if not multiplicidad:
        return False
    match = PATRON_MULTIPLICIDAD.match(multiplicidad)
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
    # Si el tipo es una enumeración del diagrama: sus literales (para @Enumerated
    # y los datos de ejemplo). None = no es enumeración.
    literales_enum: list[str] | None = None

    @property
    def es_enum(self) -> bool:
        return self.literales_enum is not None


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
    nombre: str  # identificador del stub en el Service (todo el texto, como siempre)
    # Firma parseada de "nombre(param: Tipo): Retorno", con tipos ya en Java.
    nombre_java: str = ""
    parametros: list[tuple[str, str]] = field(default_factory=list)
    retorno_java: str = "void"
    estatico: bool = False

    def clave_firma(self) -> tuple:
        return (self.nombre_java, tuple(tipo for _, tipo in self.parametros))


@dataclass
class EnumeracionModelo:
    nombre_original: str
    nombre_java: str
    literales: list[str] = field(default_factory=list)


@dataclass
class InterfazModelo:
    nombre_original: str
    nombre_java: str
    metodos: list[MetodoModelo] = field(default_factory=list)
    extiende: list[str] = field(default_factory=list)  # otras interfaces (nombre_java)


@dataclass
class EntidadModelo:
    nombre_original: str
    nombre_java: str
    campo_id_nombre: str
    campo_id_tipo: str
    campo_id_generado: bool  # False si el usuario ya definía un atributo "id"
    campos: list[CampoModelo] = field(default_factory=list)
    metodos: list[MetodoModelo] = field(default_factory=list)  # de instancia: stubs del Service
    extiende: str | None = None  # nombre_java de la superclase
    tiene_subclases: bool = False
    relaciones: list[RelacionModelo] = field(default_factory=list)
    endpoint: str = ""
    es_abstracta: bool = False
    implementa: list[str] = field(default_factory=list)  # interfaces (nombre_java)
    campos_estaticos: list[CampoModelo] = field(default_factory=list)  # no son columnas
    metodos_estaticos: list[MetodoModelo] = field(default_factory=list)

    def nombres_ocupados(self) -> set[str]:
        ocupados = {self.campo_id_nombre}
        ocupados.update(c.nombre for c in self.campos)
        ocupados.update(c.nombre for c in self.campos_estaticos)
        ocupados.update(r.nombre for r in self.relaciones)
        return ocupados


@dataclass
class ModeloBackend:
    paquete: str
    entidades: list[EntidadModelo]  # solo lo persistible: clases y clases abstractas
    enumeraciones: list[EnumeracionModelo] = field(default_factory=list)
    interfaces: list[InterfazModelo] = field(default_factory=list)
    # Lo del diagrama que no tiene traducción a código (se lista en el README).
    advertencias: list[str] = field(default_factory=list)


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


def relaciones_heredadas(entidad: EntidadModelo, entidades_por_nombre: dict[str, EntidadModelo]) -> list[RelacionModelo]:
    """Relaciones declaradas en las superclases (la FK vive en la tabla de la
    superclase, pero la subclase también las tiene). Mismo recorrido que
    `campos_heredados`; sin esto el DTO/Service de la subclase (CU11) y su
    formulario Flutter (CU12) las perdían."""
    heredadas: list[RelacionModelo] = []
    nombre_superclase = entidad.extiende
    while nombre_superclase:
        superclase = entidades_por_nombre[nombre_superclase]
        heredadas = list(superclase.relaciones) + heredadas
        nombre_superclase = superclase.extiende
    return heredadas


def todas_las_relaciones(entidad: EntidadModelo, entidades_por_nombre: dict[str, EntidadModelo]) -> list[RelacionModelo]:
    """`relaciones_heredadas` + las propias de `entidad`."""
    return relaciones_heredadas(entidad, entidades_por_nombre) + entidad.relaciones


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


_TIPOS_JAVA_DIRECTOS = {
    "void", "int", "long", "double", "float", "boolean", "char", "byte", "short",
    "String", "Integer", "Long", "Double", "Float", "Boolean", "Character", "Object",
}
# En firmas de métodos van con nombre calificado para no tener que calcular imports.
_CALIFICADOS = {
    "LocalDate": "java.time.LocalDate",
    "BigDecimal": "java.math.BigDecimal",
    "List<String>": "java.util.List<String>",
}


def _tipo_java_firma(tipo: str | None, nombres_modelo: set[str], por_defecto: str) -> str:
    """Tipo Java de un parámetro o retorno escrito a mano en el diagrama. Lo que
    no se reconoce (ni tipo del selector, ni tipo Java simple, ni una clase del
    diagrama) queda como `por_defecto`, para que el proyecto siempre compile."""
    texto = (tipo or "").strip()
    if not texto:
        return por_defecto
    mapeado = TIPOS_DATO_A_JAVA.get(texto.lower())
    if mapeado:
        return _CALIFICADOS.get(mapeado, mapeado)
    if texto in _TIPOS_JAVA_DIRECTOS:
        return texto
    como_clase = _a_identificador(texto, mayuscula_inicial=True, respaldo="")
    return como_clase if como_clase in nombres_modelo else por_defecto


def _construir_metodo(metodo: dict, nombres_modelo: set[str]) -> MetodoModelo:
    nombre, parametros, retorno = parsear_firma(metodo["texto"])
    retorno = retorno or (metodo.get("tipo") or "").strip() or None
    params_java: list[tuple[str, str]] = []
    usados: set[str] = set()
    for posicion, (nombre_param, tipo_param) in enumerate(parametros, start=1):
        identificador = _a_identificador(nombre_param, mayuscula_inicial=False, respaldo=f"p{posicion}")
        if identificador in usados:
            identificador = f"{identificador}{posicion}"
        usados.add(identificador)
        params_java.append((identificador, _tipo_java_firma(tipo_param, nombres_modelo, "Object")))
    return MetodoModelo(
        nombre=_a_identificador(metodo["texto"], mayuscula_inicial=False, respaldo="metodo"),
        nombre_java=_a_identificador(nombre, mayuscula_inicial=False, respaldo="metodo"),
        parametros=params_java,
        retorno_java=_tipo_java_firma(retorno, nombres_modelo, "void"),
        estatico=metodo.get("estatico") is True,
    )


def _a_constante(texto: str) -> str:
    partes = [p for p in re.split(r"[^a-zA-Z0-9]+", _quitar_diacriticos(texto or "")) if p]
    constante = "_".join(p.upper() for p in partes)
    return f"_{constante}" if constante[:1].isdigit() else constante


def _construir_enumeracion(node: dict) -> EnumeracionModelo:
    literales: list[str] = []
    for literal in node["data"]["atributos"]:
        constante = _a_constante(literal["texto"])
        if constante and constante not in literales:
            literales.append(constante)
    nombre_original = node["data"]["nombre"]
    return EnumeracionModelo(
        nombre_original=nombre_original,
        nombre_java=_a_identificador(nombre_original, mayuscula_inicial=True, respaldo="Enumeracion"),
        literales=literales,
    )


def _construir_interfaz(node: dict, nombres_modelo: set[str]) -> InterfazModelo:
    nombre_original = node["data"]["nombre"]
    return InterfazModelo(
        nombre_original=nombre_original,
        nombre_java=_a_identificador(nombre_original, mayuscula_inicial=True, respaldo="Interfaz"),
        metodos=[_construir_metodo(m, nombres_modelo) for m in node["data"]["metodos"]],
    )


def _construir_campo(atributo: dict, enumeraciones: dict[str, EnumeracionModelo]) -> CampoModelo:
    nombre_campo = _a_identificador(atributo["texto"], mayuscula_inicial=False, respaldo="campo")
    enumeracion = enumeraciones.get(normalizar(atributo["tipo"])) if atributo["tipo"] else None
    if enumeracion is not None:
        return CampoModelo(nombre=nombre_campo, tipo_java=enumeracion.nombre_java, literales_enum=enumeracion.literales)
    tipo_java, es_lista = _tipo_java_de(atributo["tipo"])
    return CampoModelo(nombre=nombre_campo, tipo_java=tipo_java, es_lista=es_lista)


def _construir_entidad(
    node: dict,
    enumeraciones: dict[str, EnumeracionModelo] | None = None,
    nombres_modelo: set[str] | None = None,
) -> EntidadModelo:
    enumeraciones = enumeraciones or {}
    nombres_modelo = nombres_modelo or set()
    nombre_original = node["data"]["nombre"]
    nombre_java = _a_identificador(nombre_original, mayuscula_inicial=True, respaldo="Clase")

    atributo_id = next(
        (
            a
            for a in node["data"]["atributos"]
            if _quitar_diacriticos(a["texto"]).strip().lower() == "id" and not a.get("estatico")
        ),
        None,
    )
    if atributo_id is not None:
        tipo_id, _ = _tipo_java_de(atributo_id["tipo"])
        campo_id_nombre, campo_id_tipo, campo_id_generado = "id", tipo_id, False
    else:
        campo_id_nombre, campo_id_tipo, campo_id_generado = "id", "Long", True

    campos, campos_estaticos = [], []
    for atributo in node["data"]["atributos"]:
        if atributo is atributo_id:
            continue
        campo = _construir_campo(atributo, enumeraciones)
        (campos_estaticos if atributo.get("estatico") else campos).append(campo)

    metodos_todos = [_construir_metodo(m, nombres_modelo) for m in node["data"]["metodos"]]

    return EntidadModelo(
        nombre_original=nombre_original,
        nombre_java=nombre_java,
        campo_id_nombre=campo_id_nombre,
        campo_id_tipo=campo_id_tipo,
        campo_id_generado=campo_id_generado,
        campos=campos,
        metodos=[m for m in metodos_todos if not m.estatico],
        endpoint=_endpoint_de(nombre_java),
        es_abstracta=node["data"].get("tipoClase") == "abstracta",
        campos_estaticos=campos_estaticos,
        metodos_estaticos=[m for m in metodos_todos if m.estatico],
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


def _procesar_clase_asociacion(edge: dict, entidades_por_id: dict[str, EntidadModelo]) -> None:
    """Asociación con clase intermedia X entre A y B: se descompone en
    X *-- 1 A y X *-- 1 B (X es dueña de ambas FK) y A/B ven a X como
    colección inversa. No se genera la relación directa A <-> B."""
    intermedia = entidades_por_id[edge["data"]["claseAsociacion"]]
    extremos = [entidades_por_id[edge["source"]], entidades_por_id[edge["target"]]]
    nombre_inverso = _pluralizar(_a_identificador(intermedia.nombre_java, mayuscula_inicial=False, respaldo="relacion"))

    for extremo in extremos:
        # Se agrega cada relación antes de calcular la siguiente para que
        # `_nombre_unico` distinga una autoasociación (A == B): "a" y "a2".
        rel_intermedia = RelacionModelo(
            "manyToOne",
            _nombre_unico(intermedia, _a_identificador(extremo.nombre_java, mayuscula_inicial=False, respaldo="relacion")),
            extremo.nombre_java,
            False,
            propietaria=True,
        )
        intermedia.relaciones.append(rel_intermedia)

        rel_extremo = RelacionModelo(
            "oneToMany",
            _nombre_unico(extremo, nombre_inverso),
            intermedia.nombre_java,
            True,
            propietaria=False,
            mapped_by=rel_intermedia.nombre,
        )
        extremo.relaciones.append(rel_extremo)


def _procesar_relacion_asociativa(edge: dict, entidades_por_id: dict[str, EntidadModelo]) -> None:
    data = edge["data"]
    tipo = data["tipo"]
    if tipo == "asociacion" and data.get("claseAsociacion"):
        _procesar_clase_asociacion(edge, entidades_por_id)
        return
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


_ETIQUETA_RELACION = {
    "asociacion": "asociación",
    "agregacion": "agregación",
    "composicion": "composición",
    "herencia": "herencia",
    "realizacion": "realización",
}


def construir_modelo_backend(contenido: dict, nombre_proyecto: str) -> ModeloBackend:
    contenido = validar_contenido(contenido)
    nodes, edges = contenido["nodes"], contenido["edges"]

    if not nodes:
        raise GeneracionInvalidaError("El diagrama no tiene ninguna clase definida.")

    def de_tipo(*tipos: str) -> list[dict]:
        return [n for n in nodes if n["data"]["tipoClase"] in tipos]

    nombres_modelo = {_a_identificador(n["data"]["nombre"], mayuscula_inicial=True, respaldo="Clase") for n in nodes}

    enumeraciones_por_id = {n["id"]: _construir_enumeracion(n) for n in de_tipo("enumeracion")}
    # Un atributo puede escribir el tipo como el nombre de la enumeración o como su nombre Java.
    enumeraciones_por_clave: dict[str, EnumeracionModelo] = {}
    for enumeracion in enumeraciones_por_id.values():
        enumeraciones_por_clave[normalizar(enumeracion.nombre_original)] = enumeracion
        enumeraciones_por_clave[normalizar(enumeracion.nombre_java)] = enumeracion

    interfaces_por_id = {n["id"]: _construir_interfaz(n, nombres_modelo) for n in de_tipo("interfaz")}
    entidades_por_id = {
        n["id"]: _construir_entidad(n, enumeraciones_por_clave, nombres_modelo) for n in de_tipo("clase", "abstracta")
    }

    nombres_vistos: dict[str, str] = {}
    for elemento in [*entidades_por_id.values(), *enumeraciones_por_id.values(), *interfaces_por_id.values()]:
        if elemento.nombre_java in nombres_vistos:
            otra = nombres_vistos[elemento.nombre_java]
            raise GeneracionInvalidaError(
                f'Las clases "{otra}" y "{elemento.nombre_original}" generan el mismo nombre de clase Java '
                f'("{elemento.nombre_java}"); renombrá una para poder generar el backend.'
            )
        nombres_vistos[elemento.nombre_java] = elemento.nombre_original

    nombre_nodo = {n["id"]: n["data"]["nombre"] for n in nodes}
    advertencias: list[str] = []

    def omitir(edge: dict, motivo: str) -> None:
        etiqueta = _ETIQUETA_RELACION.get(edge["data"]["tipo"], "relación")
        advertencias.append(
            f'La {etiqueta} entre "{nombre_nodo[edge["source"]]}" y "{nombre_nodo[edge["target"]]}" '
            f"no se generó: {motivo}."
        )

    def implementar(origen_id: str, interfaz_id: str) -> None:
        nombre = interfaces_por_id[interfaz_id].nombre_java
        if origen_id in entidades_por_id:
            lista = entidades_por_id[origen_id].implementa
        else:
            lista = interfaces_por_id[origen_id].extiende  # una interfaz que extiende a otra
        if nombre not in lista:
            lista.append(nombre)

    for edge in edges:
        tipo, origen, destino = edge["data"]["tipo"], edge["source"], edge["target"]
        origen_valido = origen in entidades_por_id or origen in interfaces_por_id
        if tipo == "herencia":
            if origen in entidades_por_id and destino in entidades_por_id:
                _procesar_herencia(edge, entidades_por_id)
            elif origen_valido and destino in interfaces_por_id:
                # Clase -> interfaz: en UML es una realización, pero se genera igual `implements`.
                implementar(origen, destino)
            else:
                omitir(edge, "una herencia solo se genera entre clases o entre interfaces")
        elif tipo == "realizacion":
            if origen_valido and destino in interfaces_por_id:
                implementar(origen, destino)
            else:
                omitir(edge, "solo se genera como `implements` cuando apunta a una interfaz")

    for edge in edges:
        tipo = edge["data"]["tipo"]
        if tipo not in ("asociacion", "agregacion", "composicion"):
            # "dependencia" no genera código: es una relación de uso, no de persistencia.
            continue
        extremos = [edge["source"], edge["target"], edge["data"].get("claseAsociacion")]
        if any(e is not None and e not in entidades_por_id for e in extremos):
            omitir(edge, "las interfaces y enumeraciones no son tablas, así que no se pueden relacionar con JPA")
            continue
        _procesar_relacion_asociativa(edge, entidades_por_id)

    paquete = "com.generado." + (_a_identificador(nombre_proyecto, mayuscula_inicial=False, respaldo="proyecto").lower() or "proyecto")
    paquete = re.sub(r"[^a-z0-9.]", "", paquete) or "com.generado.proyecto"

    return ModeloBackend(
        paquete=paquete,
        entidades=list(entidades_por_id.values()),
        enumeraciones=list(enumeraciones_por_id.values()),
        interfaces=list(interfaces_por_id.values()),
        advertencias=advertencias,
    )
