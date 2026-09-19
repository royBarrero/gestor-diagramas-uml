"""Enums cerrados del `contenido` del diagrama, compartidos por los
servicios de voz (CU08), digitalización por imagen (CU09) y
exportación/importación (CU10).
"""

import unicodedata

VISIBILIDADES = ("publico", "privado", "protegido")
TIPOS_RELACION = ("asociacion", "herencia", "agregacion", "composicion", "dependencia")


def normalizar(texto: str | None) -> str:
    """Minúsculas, sin espacios en los extremos y sin diacríticos (tildes,
    diéresis), para comparar nombres de clases/atributos de forma tolerante
    a cómo los transcriba el reconocimiento por voz o por imagen (CU08/CU09) —
    por ejemplo "Préstamo" y "Prestamo" deben matchear entre sí.
    """
    texto_normalizado = unicodedata.normalize("NFKD", (texto or "").strip().lower())
    return "".join(c for c in texto_normalizado if not unicodedata.combining(c))
