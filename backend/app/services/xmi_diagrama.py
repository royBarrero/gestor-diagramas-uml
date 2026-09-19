"""CU10: exportación e importación de diagramas en formato XMI 2.1 / UML2
(el estándar que entiende Enterprise Architect), a diferencia del JSON de
`exportacion_diagrama.py` que es el formato propio del proyecto.

No hay un archivo de referencia real exportado desde Enterprise Architect
contra el cual validar esto, así que el mapeo sigue el estándar UML2 tal
como lo documenta el OMG, con supuestos razonables donde el metamodelo no
alcanza a cubrir lo que modela el diagrama:

- Las posiciones (x, y) de las clases en el lienzo NO viajan en el XMI: no
  son parte del metamodelo semántico de UML (en Enterprise Architect viven
  en una extensión propietaria `<xmi:Extension extender="Enterprise
  Architect">` con el layout del diagrama, que no replicamos por no tener
  un archivo real para calcar su forma exacta). Al importar, las clases se
  reacomodan en una grilla.
- El tipo de dato de un atributo (`atributos[].tipo`) se modela como un
  `uml:PrimitiveType` propio del modelo (uno por cada nombre de tipo
  distinto usado), referenciado por `type` en el `ownedAttribute`. No se
  intenta resolver contra la librería de tipos primitivos de UML.
- La multiplicidad de un extremo de relación solo viaja si el texto libre
  que cargó el usuario matchea un patrón reconocible (`"1"`, `"0..1"`,
  `"0..*"`, `"*"`). Texto libre no estándar (ej. "muchos") no tiene
  representación en UML y se descarta en el export.
- Composición/Agregación: el rombo se dibuja del lado de la clase "todo"
  (`source` en el modelo de datos de este proyecto). El extremo `ownedEnd`
  del lado "parte" (`target`) es el que lleva `aggregation="composite"` o
  `"shared"`, siguiendo la convención habitual de las herramientas UML.
- Herencia: `generalization` queda anidado en la clase `source` (subclase),
  con `general` apuntando al id de la clase `target` (superclase) — mismo
  criterio que ya usa `RelacionEdge.jsx` para dibujar el triángulo en el
  extremo `target`.
"""

import re
from xml.etree import ElementTree as ET

from app.services.exportacion_diagrama import ArchivoInvalidoError, validar_contenido

NS_XMI = "http://schema.omg.org/spec/XMI/2.1"
NS_UML = "http://schema.omg.org/spec/UML/2.1"
XMI_TYPE = f"{{{NS_XMI}}}type"
XMI_ID = f"{{{NS_XMI}}}id"

ET.register_namespace("xmi", NS_XMI)
ET.register_namespace("uml", NS_UML)

_VISIBILIDAD_A_UML = {"publico": "public", "privado": "private", "protegido": "protected"}
_VISIBILIDAD_DESDE_UML = {v: k for k, v in _VISIBILIDAD_A_UML.items()}

_PATRON_MULTIPLICIDAD = re.compile(r"^\s*(\d+|\*)\s*(?:\.\.\s*(\d+|\*)\s*)?$")


def _slug(texto: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (texto or "").lower()).strip("-")
    return slug or "tipo"


def _multiplicidad_a_valores(texto: str | None) -> tuple[str, str] | None:
    if not texto:
        return None
    match = _PATRON_MULTIPLICIDAD.match(texto)
    if not match:
        return None
    lower, upper = match.group(1), match.group(2)
    if upper is None:
        upper = lower
    if lower == "*":
        lower = "0"
    return lower, upper


def _agregar_multiplicidad(elem_end: ET.Element, multiplicidad: str | None) -> None:
    valores = _multiplicidad_a_valores(multiplicidad)
    if valores is None:
        return
    lower, upper = valores
    lower_elem = ET.SubElement(elem_end, "lowerValue")
    lower_elem.set(XMI_TYPE, "uml:LiteralInteger")
    lower_elem.set("value", lower)
    upper_elem = ET.SubElement(elem_end, "upperValue")
    upper_elem.set(XMI_TYPE, "uml:LiteralUnlimitedNatural" if upper == "*" else "uml:LiteralInteger")
    upper_elem.set("value", upper)


def _leer_multiplicidad(elem_end: ET.Element) -> str | None:
    lower_elem = elem_end.find("lowerValue")
    upper_elem = elem_end.find("upperValue")
    lower = lower_elem.get("value") if lower_elem is not None else None
    upper = upper_elem.get("value") if upper_elem is not None else None
    if lower is None and upper is None:
        return None
    if lower is None:
        lower = upper
    if upper is None:
        upper = lower
    return lower if lower == upper else f"{lower}..{upper}"


def contenido_a_xmi(contenido: dict, nombre_diagrama: str) -> str:
    contenido = validar_contenido(contenido)
    nodes, edges = contenido["nodes"], contenido["edges"]

    xmi = ET.Element(f"{{{NS_XMI}}}XMI")
    xmi.set(f"{{{NS_XMI}}}version", "2.1")
    modelo = ET.SubElement(xmi, f"{{{NS_UML}}}Model")
    modelo.set(XMI_ID, "modelo-diagrama")
    modelo.set("name", nombre_diagrama or "Diagrama")

    tipos_primitivos: dict[str, str] = {}

    def id_tipo_primitivo(nombre_tipo: str) -> str:
        if nombre_tipo not in tipos_primitivos:
            tipos_primitivos[nombre_tipo] = f"tipo-{_slug(nombre_tipo)}"
        return tipos_primitivos[nombre_tipo]

    elementos_clase: dict[str, ET.Element] = {}
    for node in nodes:
        clase = ET.SubElement(modelo, "packagedElement")
        clase.set(XMI_TYPE, "uml:Class")
        clase.set(XMI_ID, node["id"])
        clase.set("name", node["data"]["nombre"])
        elementos_clase[node["id"]] = clase

        for atributo in node["data"]["atributos"]:
            attr_elem = ET.SubElement(clase, "ownedAttribute")
            attr_elem.set(XMI_TYPE, "uml:Property")
            attr_elem.set(XMI_ID, atributo["id"])
            attr_elem.set("name", atributo["texto"])
            attr_elem.set("visibility", _VISIBILIDAD_A_UML[atributo["visibilidad"]])
            if atributo["tipo"]:
                attr_elem.set("type", id_tipo_primitivo(atributo["tipo"]))

        for metodo in node["data"]["metodos"]:
            op_elem = ET.SubElement(clase, "ownedOperation")
            op_elem.set(XMI_TYPE, "uml:Operation")
            op_elem.set(XMI_ID, metodo["id"])
            op_elem.set("name", metodo["texto"])
            op_elem.set("visibility", _VISIBILIDAD_A_UML[metodo["visibilidad"]])

    for nombre_tipo, id_tipo in tipos_primitivos.items():
        tipo_elem = ET.SubElement(modelo, "packagedElement")
        tipo_elem.set(XMI_TYPE, "uml:PrimitiveType")
        tipo_elem.set(XMI_ID, id_tipo)
        tipo_elem.set("name", nombre_tipo)

    for edge in edges:
        data = edge["data"]
        tipo = data["tipo"]
        origen_id, destino_id = edge["source"], edge["target"]

        if tipo == "herencia":
            gen_elem = ET.SubElement(elementos_clase[origen_id], "generalization")
            gen_elem.set(XMI_TYPE, "uml:Generalization")
            gen_elem.set(XMI_ID, edge["id"])
            gen_elem.set("general", destino_id)
            continue

        if tipo == "dependencia":
            dep_elem = ET.SubElement(modelo, "packagedElement")
            dep_elem.set(XMI_TYPE, "uml:Dependency")
            dep_elem.set(XMI_ID, edge["id"])
            if data["nombre"]:
                dep_elem.set("name", data["nombre"])
            dep_elem.set("client", origen_id)
            dep_elem.set("supplier", destino_id)
            continue

        assoc_elem = ET.SubElement(modelo, "packagedElement")
        assoc_elem.set(XMI_TYPE, "uml:Association")
        assoc_elem.set(XMI_ID, edge["id"])
        if data["nombre"]:
            assoc_elem.set("name", data["nombre"])

        extremo_origen = ET.SubElement(assoc_elem, "ownedEnd")
        extremo_origen.set(XMI_TYPE, "uml:Property")
        extremo_origen.set(XMI_ID, f"{edge['id']}-origen")
        extremo_origen.set("type", origen_id)
        _agregar_multiplicidad(extremo_origen, data["multiplicidadOrigen"])

        extremo_destino = ET.SubElement(assoc_elem, "ownedEnd")
        extremo_destino.set(XMI_TYPE, "uml:Property")
        extremo_destino.set(XMI_ID, f"{edge['id']}-destino")
        extremo_destino.set("type", destino_id)
        if tipo in ("agregacion", "composicion"):
            extremo_destino.set("aggregation", "composite" if tipo == "composicion" else "shared")
        _agregar_multiplicidad(extremo_destino, data["multiplicidadDestino"])

    ET.indent(xmi, space="  ")
    return ET.tostring(xmi, encoding="unicode", xml_declaration=True)


def xmi_a_contenido(archivo_bytes: bytes) -> dict:
    try:
        texto = archivo_bytes.decode("utf-8")
        xmi = ET.fromstring(texto)
    except (UnicodeDecodeError, ET.ParseError) as exc:
        raise ArchivoInvalidoError("El archivo no es un XML válido.") from exc

    modelo = xmi.find(f"{{{NS_UML}}}Model")
    if modelo is None:
        raise ArchivoInvalidoError("El archivo no tiene la estructura de un modelo UML (falta uml:Model).")

    tipos_primitivos: dict[str, str] = {}
    for elem in modelo.findall("packagedElement"):
        if elem.get(XMI_TYPE) == "uml:PrimitiveType":
            tipos_primitivos[elem.get(XMI_ID)] = elem.get("name", "")

    nodes = []
    ids_nodos = set()
    generalizaciones = []  # (edge_id, origen_id, destino_id)
    for elem in modelo.findall("packagedElement"):
        if elem.get(XMI_TYPE) != "uml:Class":
            continue
        clase_id = elem.get(XMI_ID)
        nombre = elem.get("name")
        if not clase_id or not nombre:
            raise ArchivoInvalidoError("Hay una clase sin id o sin nombre en el archivo.")
        if clase_id in ids_nodos:
            raise ArchivoInvalidoError(f'El id "{clase_id}" está repetido entre las clases.')
        ids_nodos.add(clase_id)

        atributos = []
        for attr_elem in elem.findall("ownedAttribute"):
            visibilidad = _VISIBILIDAD_DESDE_UML.get(attr_elem.get("visibility"), "publico")
            atributos.append(
                {
                    "id": attr_elem.get(XMI_ID) or f"{clase_id}-attr-{len(atributos)}",
                    "visibilidad": visibilidad,
                    "tipo": tipos_primitivos.get(attr_elem.get("type"), ""),
                    "texto": attr_elem.get("name", ""),
                }
            )

        metodos = []
        for op_elem in elem.findall("ownedOperation"):
            visibilidad = _VISIBILIDAD_DESDE_UML.get(op_elem.get("visibility"), "publico")
            metodos.append(
                {
                    "id": op_elem.get(XMI_ID) or f"{clase_id}-op-{len(metodos)}",
                    "visibilidad": visibilidad,
                    "tipo": "",
                    "texto": op_elem.get("name", ""),
                }
            )

        columna, fila = len(nodes) % 4, len(nodes) // 4
        nodes.append(
            {
                "id": clase_id,
                "type": "clase",
                "position": {"x": 80 + columna * 260, "y": 80 + fila * 220},
                "data": {"nombre": nombre, "atributos": atributos, "metodos": metodos},
            }
        )

        for gen_elem in elem.findall("generalization"):
            general = gen_elem.get("general")
            if not general:
                continue
            generalizaciones.append((gen_elem.get(XMI_ID) or f"gen-{clase_id}-{general}", clase_id, general))

    edges = []
    ids_edges = set()

    def agregar_edge(edge_id, source, target, data):
        if not edge_id or edge_id in ids_edges:
            edge_id = f"{edge_id or 'rel'}-{len(edges)}"
        ids_edges.add(edge_id)
        edges.append({"id": edge_id, "source": source, "target": target, "type": "relacion", "data": data})

    for edge_id, origen_id, destino_id in generalizaciones:
        agregar_edge(
            edge_id,
            origen_id,
            destino_id,
            {
                "tipo": "herencia",
                "multiplicidadOrigen": None,
                "multiplicidadDestino": None,
                "nombre": None,
                "estiloLinea": "recta",
            },
        )

    for elem in modelo.findall("packagedElement"):
        tipo_xmi = elem.get(XMI_TYPE)

        if tipo_xmi == "uml:Dependency":
            agregar_edge(
                elem.get(XMI_ID),
                elem.get("client"),
                elem.get("supplier"),
                {
                    "tipo": "dependencia",
                    "multiplicidadOrigen": None,
                    "multiplicidadDestino": None,
                    "nombre": elem.get("name"),
                    "estiloLinea": "recta",
                },
            )
            continue

        if tipo_xmi != "uml:Association":
            continue

        extremos = elem.findall("ownedEnd")
        if len(extremos) != 2:
            raise ArchivoInvalidoError(f'La asociación "{elem.get(XMI_ID)}" no tiene dos extremos.')

        extremo_parte = next((e for e in extremos if e.get("aggregation") in ("composite", "shared")), None)
        if extremo_parte is not None:
            extremo_destino = extremo_parte
            extremo_origen = next(e for e in extremos if e is not extremo_parte)
            tipo = "composicion" if extremo_parte.get("aggregation") == "composite" else "agregacion"
        else:
            extremo_origen, extremo_destino = extremos
            tipo = "asociacion"

        agregar_edge(
            elem.get(XMI_ID),
            extremo_origen.get("type"),
            extremo_destino.get("type"),
            {
                "tipo": tipo,
                "multiplicidadOrigen": _leer_multiplicidad(extremo_origen),
                "multiplicidadDestino": _leer_multiplicidad(extremo_destino),
                "nombre": elem.get("name"),
                "estiloLinea": "recta",
            },
        )

    return validar_contenido({"nodes": nodes, "edges": edges})
