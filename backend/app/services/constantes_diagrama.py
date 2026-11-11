"""Enums cerrados del `contenido` del diagrama, compartidos por los
servicios de voz (CU08), digitalización por imagen (CU09) y
exportación/importación (CU10).
"""

import re
import unicodedata

VISIBILIDADES = ("publico", "privado", "protegido", "paquete")
TIPOS_RELACION = ("asociacion", "herencia", "agregacion", "composicion", "dependencia", "realizacion")
# Clasificador UML de cada nodo (`data.tipoClase`). Un nodo sin el campo es "clase"
# (diagramas guardados antes de que existiera). Espejo: frontend/src/constants/tiposClase.js.
TIPOS_CLASE = ("clase", "abstracta", "interfaz", "enumeracion")

# Tipos de dato de un atributo, con el nombre que muestra el editor y su tipo Java
# en el backend generado (CU11). Es la única fuente: agregar uno acá también lo
# habilita para el agente (CU17). El selector del editor es
# frontend/src/constants/tiposDato.js.
TIPOS_DATO = {
    "String": "String",
    "int": "int",
    "long": "long",
    "double": "double",
    "float": "float",
    "boolean": "boolean",
    "char": "char",
    "Date": "LocalDate",
    "List": "List<String>",
    "Decimal": "BigDecimal",
}
TIPOS_DATO_A_JAVA = {nombre.lower(): java for nombre, java in TIPOS_DATO.items()}
_NOMBRES_TIPOS_DATO = {nombre.lower(): nombre for nombre in TIPOS_DATO}

PATRON_MULTIPLICIDAD = re.compile(r"^\s*(\d+|\*)\s*(?:\.\.\s*(\d+|\*)\s*)?$")


def tipo_dato_canonico(tipo: str | None) -> str | None:
    """El nombre del selector para `tipo` en cualquier grafía, o None si no es un
    tipo que acepte el generador."""
    return _NOMBRES_TIPOS_DATO.get((tipo or "").strip().lower())


def multiplicidad_valida(multiplicidad: str | None) -> bool:
    """`1`, `*`, `0..*`, `2..5`; no `5..2` ni `*..1`."""
    coincidencia = PATRON_MULTIPLICIDAD.match(multiplicidad or "")
    if not coincidencia:
        return False
    minimo, maximo = coincidencia.group(1), coincidencia.group(2)
    if maximo is None or maximo == "*":
        return True
    return minimo != "*" and int(minimo) <= int(maximo)


def normalizar(texto: str | None) -> str:
    """Minúsculas, sin espacios en los extremos y sin diacríticos (tildes,
    diéresis), para comparar nombres de clases/atributos de forma tolerante
    a cómo los transcriba el reconocimiento por voz o por imagen (CU08/CU09) —
    por ejemplo "Préstamo" y "Prestamo" deben matchear entre sí.
    """
    texto_normalizado = unicodedata.normalize("NFKD", (texto or "").strip().lower())
    return "".join(c for c in texto_normalizado if not unicodedata.combining(c))


_PATRON_FIRMA = re.compile(r"^\s*([^()]*?)\s*\((.*)\)\s*(?::\s*(.*?))?\s*$")


def parsear_firma(texto: str) -> tuple[str, list[tuple[str, str]], str | None]:
    """Separa el texto libre de un método con el formato
    "nombre(param: tipo, ...): tipoRetorno" en (nombre, [(param, tipo)], retorno).
    La usan el XMI (CU10) y la generación de código (CU11).
    Paréntesis, parámetros y retorno son opcionales; lo que falte queda vacío
    (lista vacía / None)."""
    texto = (texto or "").strip()
    match = _PATRON_FIRMA.match(texto)
    if match:
        nombre, texto_params, retorno = match.group(1), match.group(2), match.group(3)
    else:
        nombre, _, retorno = texto.partition(":")
        texto_params = ""

    parametros = []
    for parte in texto_params.split(","):
        if not parte.strip():
            continue
        nombre_param, _, tipo_param = parte.partition(":")
        parametros.append((nombre_param.strip(), tipo_param.strip()))

    return nombre.strip() or texto, parametros, (retorno or "").strip() or None
