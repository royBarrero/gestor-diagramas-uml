"""CU10: exportación e importación de diagramas en el formato JSON nativo
del proyecto (el mismo shape {"nodes", "edges"} que ya persiste el modelo
`Diagrama`). El formato XMI vive en `xmi_diagrama.py`.
"""

import json
import re

from app.services.constantes_diagrama import TIPOS_RELACION, VISIBILIDADES


class ArchivoInvalidoError(Exception):
    """El archivo no es JSON válido, o no tiene la estructura de un diagrama."""


def _validar_items(items, etiqueta: str, nombre_nodo: str) -> list[dict]:
    if items is None:
        return []
    if not isinstance(items, list):
        raise ArchivoInvalidoError(f'La clase "{nombre_nodo}" tiene "{etiqueta}" inválido.')

    validados = []
    for item in items:
        if not isinstance(item, dict) or not item.get("id"):
            raise ArchivoInvalidoError(f'La clase "{nombre_nodo}" tiene un {etiqueta[:-1]} sin id.')
        visibilidad = item.get("visibilidad")
        if visibilidad not in VISIBILIDADES:
            raise ArchivoInvalidoError(
                f'"{visibilidad}" no es una visibilidad válida en la clase "{nombre_nodo}".'
            )
        validados.append(
            {
                "id": item["id"],
                "visibilidad": visibilidad,
                "tipo": item.get("tipo", ""),
                "texto": item.get("texto", ""),
            }
        )
    return validados


def validar_contenido(contenido) -> dict:
    """Verifica que `contenido` tenga la forma {"nodes": [...], "edges": [...]}
    que espera el resto del sistema. Devuelve un dict nuevo y normalizado
    (con los campos cosméticos ausentes completados con default). Lanza
    ArchivoInvalidoError con un mensaje claro si la estructura no es válida.
    """
    if not isinstance(contenido, dict):
        raise ArchivoInvalidoError("El archivo no tiene la estructura de un diagrama.")

    nodes_in = contenido.get("nodes")
    edges_in = contenido.get("edges")
    if not isinstance(nodes_in, list) or not isinstance(edges_in, list):
        raise ArchivoInvalidoError("El archivo no tiene la estructura de un diagrama (falta 'nodes' o 'edges').")

    nodes = []
    ids_nodos = set()
    for nodo in nodes_in:
        if not isinstance(nodo, dict) or not nodo.get("id"):
            raise ArchivoInvalidoError("Hay una clase sin id en el archivo.")
        if nodo["id"] in ids_nodos:
            raise ArchivoInvalidoError(f'El id "{nodo["id"]}" está repetido entre las clases.')
        ids_nodos.add(nodo["id"])

        data = nodo.get("data") if isinstance(nodo.get("data"), dict) else {}
        nombre = data.get("nombre")
        if not isinstance(nombre, str) or not nombre.strip():
            raise ArchivoInvalidoError(f'La clase "{nodo["id"]}" no tiene nombre.')

        position = nodo.get("position") if isinstance(nodo.get("position"), dict) else {}
        nodes.append(
            {
                "id": nodo["id"],
                "type": "clase",
                "position": {"x": position.get("x", 0), "y": position.get("y", 0)},
                "data": {
                    "nombre": nombre,
                    "atributos": _validar_items(data.get("atributos"), "atributos", nombre),
                    "metodos": _validar_items(data.get("metodos"), "metodos", nombre),
                },
            }
        )

    edges = []
    ids_edges = set()
    for edge in edges_in:
        if not isinstance(edge, dict) or not edge.get("id"):
            raise ArchivoInvalidoError("Hay una relación sin id en el archivo.")
        if edge["id"] in ids_edges:
            raise ArchivoInvalidoError(f'El id "{edge["id"]}" está repetido entre las relaciones.')
        ids_edges.add(edge["id"])

        source, target = edge.get("source"), edge.get("target")
        if source not in ids_nodos or target not in ids_nodos:
            raise ArchivoInvalidoError(f'La relación "{edge["id"]}" hace referencia a una clase inexistente.')

        data = edge.get("data") if isinstance(edge.get("data"), dict) else {}
        tipo = data.get("tipo")
        if tipo not in TIPOS_RELACION:
            raise ArchivoInvalidoError(f'"{tipo}" no es un tipo de relación válido.')

        edges.append(
            {
                "id": edge["id"],
                "source": source,
                "target": target,
                "type": "relacion",
                "data": {
                    "tipo": tipo,
                    "multiplicidadOrigen": data.get("multiplicidadOrigen"),
                    "multiplicidadDestino": data.get("multiplicidadDestino"),
                    "nombre": data.get("nombre"),
                    "estiloLinea": data.get("estiloLinea", "recta"),
                },
            }
        )

    return {"nodes": nodes, "edges": edges}


def contenido_desde_json(archivo_bytes: bytes) -> dict:
    try:
        contenido = json.loads(archivo_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArchivoInvalidoError("El archivo no es un JSON válido.") from exc
    return validar_contenido(contenido)


def nombre_archivo_descarga(nombre_diagrama: str, extension: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (nombre_diagrama or "diagrama").lower()).strip("-") or "diagrama"
    return f"{slug}.{extension}"
