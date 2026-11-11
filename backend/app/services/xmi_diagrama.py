"""CU10: exportación e importación de diagramas en formato XMI 2.1 / UML2
(el estándar que entiende Enterprise Architect), a diferencia del JSON de
`exportacion_diagrama.py` que es el formato propio del proyecto.

El mapeo sigue el estándar UML2 del OMG, con la forma concreta calcada de un
XMI real exportado por Enterprise Architect: asociaciones con `memberEnd`,
`association` en cada `ownedEnd` y los tipos como hijo `<type xmi:idref>`
(sin eso EA importa las asociaciones sueltas, sin conectar a las clases), y
el "ilimitado" de la multiplicidad como `-1`. Supuestos donde el metamodelo
no alcanza a cubrir lo que modela el diagrama:

- Las posiciones (x, y) de las clases en el lienzo NO viajan en el XMI: no
  son parte del metamodelo semántico de UML (en Enterprise Architect viven
  en una extensión propietaria `<xmi:Extension extender="Enterprise
  Architect">` con el layout del diagrama, que no replicamos por no tener
  un archivo real para calcar su forma exacta). Al importar, las clases se
  reacomodan en una grilla.
- El tipo de dato de un atributo (`atributos[].tipo`) se modela como un
  `uml:PrimitiveType` propio del modelo (uno por cada nombre de tipo
  distinto usado), referenciado por `type` en el `ownedAttribute`. No se
  intenta resolver contra la librería de tipos primitivos de UML. Como EA no
  resuelve esa referencia al importar, además se escribe un bloque
  `<xmi:Extension extender="Enterprise Architect">` con solo los elementos
  (clases): tipo de cada atributo y retorno/parámetros de cada operación en
  texto plano, que es de donde EA los lee. Sin layout ni conectores. EA
  solo lee esa extensión si el archivo trae `<xmi:Documentation
  exporter="Enterprise Architect">` como primer hijo de `<xmi:XMI>`.
- Un tipo (de atributo, parámetro o retorno) que coincide exactamente con
  el nombre de una clase del diagrama referencia el xmi:id de esa clase;
  solo los demás tipos generan un `uml:PrimitiveType`.
- Métodos: el texto libre ("nombre(param: tipo, ...): retorno") se parsea;
  `name` lleva solo el nombre (con la firma completa EA muestra
  "anular(): void()"), cada parámetro va como `ownedParameter
  direction="in"` y el retorno como `ownedParameter direction="return"`. Al
  importar se rearma el texto con esa forma, así que un método guardado sin
  paréntesis ("cerrar") vuelve como "cerrar()".
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
- Clase de asociación (`data.claseAsociacion` de una relación): se exporta
  como un único `uml:AssociationClass` con el id y nombre de la clase, sus
  atributos/métodos y los extremos de la asociación — no como Class +
  Association por separado.
"""

import re
from xml.etree import ElementTree as ET

from app.services.exportacion_diagrama import ArchivoInvalidoError, validar_contenido

NS_XMI = "http://schema.omg.org/spec/XMI/2.1"
NS_UML = "http://schema.omg.org/spec/UML/2.1"
XMI_TYPE = f"{{{NS_XMI}}}type"
XMI_ID = f"{{{NS_XMI}}}id"
XMI_IDREF = f"{{{NS_XMI}}}idref"

ET.register_namespace("xmi", NS_XMI)
ET.register_namespace("uml", NS_UML)

_VISIBILIDAD_A_UML = {"publico": "public", "privado": "private", "protegido": "protected"}
_VISIBILIDAD_DESDE_UML = {v: k for k, v in _VISIBILIDAD_A_UML.items()}

_PATRON_MULTIPLICIDAD = re.compile(r"^\s*(\d+|\*)\s*(?:\.\.\s*(\d+|\*)\s*)?$")


_PATRON_FIRMA = re.compile(r"^\s*([^()]*?)\s*\((.*)\)\s*(?::\s*(.*?))?\s*$")

_VISIBILIDAD_A_SCOPE_EA = {"publico": "Public", "privado": "Private", "protegido": "Protected"}


def _parsear_firma(texto: str) -> tuple[str, list[tuple[str, str]], str | None]:
    """Separa el texto libre de un método con el formato
    "nombre(param: tipo, ...): tipoRetorno" en (nombre, [(param, tipo)], retorno).
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


def _armar_firma(nombre: str, parametros: list[tuple[str, str]], retorno: str | None) -> str:
    params = ", ".join(f"{n}: {t}" if t else n for n, t in parametros)
    firma = f"{nombre}({params})"
    return f"{firma}: {retorno}" if retorno else firma


def _nombre_tipo(ref: str | None, tipos_primitivos: dict[str, str], respaldo: str | None = None) -> str:
    """Nombre legible de un tipo referenciado por id: primero los
    uml:PrimitiveType del propio archivo, después lo que diga la extensión de
    EA (`respaldo`), y por último los ids de la librería de EA que no se
    declaran en el archivo (ej. "EAJava_String" -> "String")."""
    if ref in tipos_primitivos:
        return tipos_primitivos[ref]
    if respaldo:
        return respaldo
    if ref and ref.startswith("EA") and "_" in ref:
        return ref.split("_", 1)[1]
    return ""


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
    # EA escribe el "ilimitado" como -1, no como "*".
    upper_elem.set(XMI_TYPE, "uml:LiteralUnlimitedNatural" if upper == "*" else "uml:LiteralInteger")
    upper_elem.set("value", "-1" if upper == "*" else upper)


def _leer_multiplicidad(elem_end: ET.Element) -> str | None:
    lower_elem = elem_end.find("lowerValue")
    upper_elem = elem_end.find("upperValue")
    lower = lower_elem.get("value") if lower_elem is not None else None
    upper = upper_elem.get("value") if upper_elem is not None else None
    if upper == "-1":
        upper = "*"
    if lower is None and upper is None:
        return None
    if lower is None:
        lower = upper
    if upper is None:
        upper = lower
    return lower if lower == upper else f"{lower}..{upper}"


def _agregar_ref_tipo(elem: ET.Element, idref: str) -> None:
    """Tipo de un atributo o extremo como hijo <type xmi:idref>, como lo
    escribe EA (con el atributo plano `type="..."` EA no resuelve la
    referencia y deja las asociaciones sin clases en sus extremos)."""
    ET.SubElement(elem, "type").set(XMI_IDREF, idref)


def _ref_tipo(elem: ET.Element) -> str | None:
    """Lee el tipo en cualquiera de las dos formas: hijo <type xmi:idref>
    (formato actual, igual que EA) o atributo `type` (archivos exportados
    antes de este cambio)."""
    hijo = elem.find("type")
    if hijo is not None and hijo.get(XMI_IDREF):
        return hijo.get(XMI_IDREF)
    return elem.get("type")


def _agregar_extremos(assoc_elem: ET.Element, edge: dict) -> None:
    """memberEnd + ownedEnd de una asociación (o del lado asociación de una
    AssociationClass), con la forma exacta que usa EA: sin los memberEnd ni
    el atributo `association` en cada extremo, EA importa la asociación
    suelta, sin conectar a ninguna clase."""
    data, tipo, assoc_id = edge["data"], edge["data"]["tipo"], assoc_elem.get(XMI_ID)
    agregacion_parte = {"agregacion": "shared", "composicion": "composite"}.get(tipo, "none")
    extremos = [
        (f"{edge['id']}-origen", edge["source"], "none", data["multiplicidadOrigen"]),
        (f"{edge['id']}-destino", edge["target"], agregacion_parte, data["multiplicidadDestino"]),
    ]
    for extremo_id, *_ in extremos:
        ET.SubElement(assoc_elem, "memberEnd").set(XMI_IDREF, extremo_id)
    for extremo_id, clase_id, agregacion, multiplicidad in extremos:
        extremo = ET.SubElement(assoc_elem, "ownedEnd")
        extremo.set(XMI_TYPE, "uml:Property")
        extremo.set(XMI_ID, extremo_id)
        extremo.set("association", assoc_id)
        extremo.set("aggregation", agregacion)
        _agregar_ref_tipo(extremo, clase_id)
        _agregar_multiplicidad(extremo, multiplicidad)


def _simplificar_multiplicidad(texto: str | None) -> str | None:
    """EA escribe '1' como '1..1' en su extensión; se deja como '1' (mismo
    valor en UML) para que se vea igual que antes de pasar por EA."""
    if not texto:
        return texto
    partes = texto.split("..")
    return partes[0] if len(partes) == 2 and partes[0] == partes[1] else texto


def _visibilidad_ea(valor: str | None) -> str:
    return _VISIBILIDAD_DESDE_UML.get((valor or "").lower(), "publico")


def _indice_extension_ea(extension: ET.Element | None) -> tuple[dict[str, str], dict[str, dict]]:
    """Tipos que EA escribe en texto plano en su extensión, indexados por el
    id del elemento del modelo UML al que corresponden:
    - atributos: {id_atributo: tipo}
    - operaciones: {id_operacion: {"retorno": tipo | None,
                                   "params": [(id_parametro, tipo, nombre | None)]}}
    """
    tipos_atributos: dict[str, str] = {}
    operaciones: dict[str, dict] = {}
    elementos = extension.find("elements") if extension is not None else None
    if elementos is None:
        return tipos_atributos, operaciones

    for attr_elem in elementos.iter("attribute"):
        props = attr_elem.find("properties")
        if attr_elem.get(XMI_IDREF) and props is not None and props.get("type"):
            tipos_atributos[attr_elem.get(XMI_IDREF)] = props.get("type")

    for op_elem in elementos.iter("operation"):
        if not op_elem.get(XMI_IDREF):
            continue
        tipo_elem = op_elem.find("type")
        params = []
        params_container = op_elem.find("parameters")
        if params_container is not None:
            for param_elem in params_container.findall("parameter"):
                props = param_elem.find("properties")
                if props is not None and props.get("ck") == "return":
                    continue
                params.append(
                    (
                        param_elem.get(XMI_IDREF),
                        props.get("type", "") if props is not None else "",
                        param_elem.get("name"),
                    )
                )
        operaciones[op_elem.get(XMI_IDREF)] = {
            "retorno": (tipo_elem.get("type") or None) if tipo_elem is not None else None,
            "params": params,
        }
    return tipos_atributos, operaciones


def _agregar_extension_ea(xmi: ET.Element, nodes: list[dict], ids_clases_asociacion: set[str]) -> None:
    """Bloque propietario <xmi:Extension extender="Enterprise Architect">:
    EA ignora los <type xmi:idref> hacia uml:PrimitiveType al importar y toma
    de acá el tipo de cada atributo y el retorno/parámetros de cada operación.
    Solo los elementos (clases); el layout y los conectores no viajan."""
    extension = ET.SubElement(xmi, f"{{{NS_XMI}}}Extension")
    extension.set("extender", "Enterprise Architect")
    extension.set("extenderID", "6.5")
    elementos = ET.SubElement(extension, "elements")

    for node in nodes:
        elem = ET.SubElement(elementos, "element")
        elem.set(XMI_IDREF, node["id"])
        elem.set(XMI_TYPE, "uml:AssociationClass" if node["id"] in ids_clases_asociacion else "uml:Class")
        elem.set("name", node["data"]["nombre"])

        atributos = ET.SubElement(elem, "attributes")
        for atributo in node["data"]["atributos"]:
            attr_elem = ET.SubElement(atributos, "attribute")
            attr_elem.set(XMI_IDREF, atributo["id"])
            attr_elem.set("name", atributo["texto"])
            attr_elem.set("scope", _VISIBILIDAD_A_SCOPE_EA[atributo["visibilidad"]])
            ET.SubElement(attr_elem, "properties").set("type", atributo["tipo"] or "")

        operaciones = ET.SubElement(elem, "operations")
        for metodo in node["data"]["metodos"]:
            nombre, parametros, retorno = _firma_de_metodo(metodo)
            op_elem = ET.SubElement(operaciones, "operation")
            op_elem.set(XMI_IDREF, metodo["id"])
            op_elem.set("name", nombre)
            op_elem.set("scope", _VISIBILIDAD_A_SCOPE_EA[metodo["visibilidad"]])
            if retorno:
                ET.SubElement(op_elem, "type").set("type", retorno)
            if parametros:
                params_elem = ET.SubElement(op_elem, "parameters")
                for pos, (nombre_param, tipo_param) in enumerate(parametros):
                    param_elem = ET.SubElement(params_elem, "parameter")
                    param_elem.set(XMI_IDREF, f"{metodo['id']}-p{pos}")
                    props = ET.SubElement(param_elem, "properties")
                    props.set("pos", str(pos))
                    props.set("type", tipo_param)
                    props.set("ck", "in")


def _firma_de_metodo(metodo: dict) -> tuple[str, list[tuple[str, str]], str | None]:
    """Firma del método para exportar: lo que diga su texto y, si el texto no
    trae retorno, el `tipo` del ítem (algunos orígenes lo cargan ahí)."""
    nombre, parametros, retorno = _parsear_firma(metodo["texto"])
    return nombre, parametros, retorno or (metodo.get("tipo") or "").strip() or None


def _texto_de_operacion(op_elem: ET.Element, tipos_primitivos: dict[str, str], operaciones_ea: dict[str, dict]) -> str:
    """Reconstruye "nombre(param: tipo): retorno" a partir de los
    ownedParameter de la operación (y de la extensión de EA para los tipos
    que no se resuelven en el modelo). Un `name` que ya trae paréntesis es
    de un XMI exportado antes de este cambio (firma completa en el nombre) y
    se deja tal cual."""
    nombre = op_elem.get("name", "")
    if "(" in nombre:
        return nombre

    firma_ea = operaciones_ea.get(op_elem.get(XMI_ID), {"retorno": None, "params": []})
    tipos_params_ea = {param_id: tipo for param_id, tipo, _ in firma_ea["params"] if param_id}

    parametros = []
    retorno = None
    for param_elem in op_elem.findall("ownedParameter"):
        if param_elem.get("direction") == "return":
            retorno = _nombre_tipo(_ref_tipo(param_elem), tipos_primitivos, firma_ea["retorno"]) or None
            continue
        tipo = _nombre_tipo(_ref_tipo(param_elem), tipos_primitivos, tipos_params_ea.get(param_elem.get(XMI_ID)))
        parametros.append((param_elem.get("name") or f"p{len(parametros)}", tipo))

    return _armar_firma(nombre, parametros, retorno or firma_ea["retorno"])


def _contenido_desde_extension_ea(extension: ET.Element, nombres_parametros: dict[str, str] | None = None) -> dict | None:
    """Lector alternativo para XMI real de Enterprise Architect: en vez de
    resolver las referencias cruzadas por xmi:id/xmi:idref del <uml:Model>
    formal (que EA no expone de la forma en que este módulo la espera), lee
    el bloque propietario <xmi:Extension>, donde EA repite nombre y tipo de
    cada atributo en texto plano y cada relación trae su source/target por
    id directo. Se usa solo como fallback cuando el parser normal no
    encontró ninguna clase.
    """
    elementos = extension.find("elements")
    if elementos is None:
        return None
    _, operaciones_ea = _indice_extension_ea(extension)
    nombres_parametros = nombres_parametros or {}

    ids_clases: set[str] = set()
    nodes = []
    for elem in elementos.findall("element"):
        if elem.get(XMI_TYPE) not in ("uml:Class", "uml:AssociationClass"):
            continue
        clase_id = elem.get(XMI_IDREF)
        nombre = elem.get("name")
        if not clase_id or not nombre or clase_id in ids_clases:
            continue
        ids_clases.add(clase_id)

        atributos = []
        attrs_container = elem.find("attributes")
        if attrs_container is not None:
            for attr_elem in attrs_container.findall("attribute"):
                props = attr_elem.find("properties")
                atributos.append(
                    {
                        "id": attr_elem.get(XMI_IDREF) or f"{clase_id}-attr-{len(atributos)}",
                        "visibilidad": _visibilidad_ea(attr_elem.get("scope")),
                        "tipo": props.get("type", "") if props is not None else "",
                        "texto": attr_elem.get("name", ""),
                    }
                )

        metodos = []
        ops_container = elem.find("operations")
        if ops_container is not None:
            for op_elem in ops_container.findall("operation"):
                nombre_op = op_elem.get("name", "")
                firma = operaciones_ea.get(op_elem.get(XMI_IDREF))
                if firma is not None and "(" not in nombre_op:
                    parametros = [
                        (nombres_parametros.get(param_id) or nombre_param or f"p{pos}", tipo_param)
                        for pos, (param_id, tipo_param, nombre_param) in enumerate(firma["params"])
                    ]
                    nombre_op = _armar_firma(nombre_op, parametros, firma["retorno"])
                metodos.append(
                    {
                        "id": op_elem.get(XMI_IDREF) or f"{clase_id}-op-{len(metodos)}",
                        "visibilidad": _visibilidad_ea(op_elem.get("scope")),
                        "tipo": "",
                        "texto": nombre_op,
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

    if not nodes:
        return None

    edges = []
    ids_edges: set[str] = set()
    conectores = extension.find("connectors")
    if conectores is not None:
        for conn in conectores.findall("connector"):
            source_el, target_el = conn.find("source"), conn.find("target")
            if source_el is None or target_el is None:
                continue
            source_id, target_id = source_el.get(XMI_IDREF), target_el.get(XMI_IDREF)
            if source_id not in ids_clases or target_id not in ids_clases:
                continue

            props = conn.find("properties")
            ea_type = props.get("ea_type") if props is not None else None

            edge_id = conn.get(XMI_IDREF) or f"rel-{len(edges)}"
            if edge_id in ids_edges:
                edge_id = f"{edge_id}-{len(edges)}"
            ids_edges.add(edge_id)

            if ea_type == "Generalization":
                edges.append(
                    {
                        "id": edge_id,
                        "source": source_id,
                        "target": target_id,
                        "type": "relacion",
                        "data": {
                            "tipo": "herencia",
                            "multiplicidadOrigen": None,
                            "multiplicidadDestino": None,
                            "nombre": None,
                            "estiloLinea": "recta",
                        },
                    }
                )
                continue

            if ea_type != "Association":
                continue

            source_tipo, target_tipo = source_el.find("type"), target_el.find("type")
            agg_source = source_tipo.get("aggregation") if source_tipo is not None else "none"
            agg_target = target_tipo.get("aggregation") if target_tipo is not None else "none"
            mult_source = _simplificar_multiplicidad(source_tipo.get("multiplicity") if source_tipo is not None else None)
            mult_target = _simplificar_multiplicidad(target_tipo.get("multiplicity") if target_tipo is not None else None)

            # mismo criterio que el exportador: el rombo va del lado "todo" (origen);
            # el extremo "parte" es el que trae aggregation y pasa a ser destino.
            if agg_target in ("composite", "shared"):
                tipo = "composicion" if agg_target == "composite" else "agregacion"
                origen_id, destino_id, mult_o, mult_d = source_id, target_id, mult_source, mult_target
            elif agg_source in ("composite", "shared"):
                tipo = "composicion" if agg_source == "composite" else "agregacion"
                origen_id, destino_id, mult_o, mult_d = target_id, source_id, mult_target, mult_source
            else:
                tipo, origen_id, destino_id = "asociacion", source_id, target_id
                mult_o, mult_d = mult_source, mult_target

            # EA guarda la clase de asociación en el conector de la asociación,
            # no en la clase: <extendedProperties associationclass="EAID_...">.
            # validar_contenido descarta la referencia si no es válida.
            extendidas = conn.find("extendedProperties")
            clase_asociacion = extendidas.get("associationclass") if extendidas is not None else None

            edges.append(
                {
                    "id": edge_id,
                    "source": origen_id,
                    "target": destino_id,
                    "type": "relacion",
                    "data": {
                        "tipo": tipo,
                        "multiplicidadOrigen": mult_o,
                        "multiplicidadDestino": mult_d,
                        "nombre": props.get("name") if props is not None else None,
                        "estiloLinea": "recta",
                        "claseAsociacion": clase_asociacion,
                    },
                }
            )

    return validar_contenido({"nodes": nodes, "edges": edges})


def contenido_a_xmi(contenido: dict, nombre_diagrama: str) -> str:
    contenido = validar_contenido(contenido)
    nodes, edges = contenido["nodes"], contenido["edges"]

    xmi = ET.Element(f"{{{NS_XMI}}}XMI")
    xmi.set(f"{{{NS_XMI}}}version", "2.1")
    # Sin esta marca EA ignora el bloque <xmi:Extension> (y con él los tipos).
    documentacion = ET.SubElement(xmi, f"{{{NS_XMI}}}Documentation")
    documentacion.set("exporter", "Enterprise Architect")
    documentacion.set("exporterVersion", "6.5")
    modelo = ET.SubElement(xmi, f"{{{NS_UML}}}Model")
    modelo.set(XMI_ID, "modelo-diagrama")
    modelo.set("name", nombre_diagrama or "Diagrama")

    tipos_primitivos: dict[str, str] = {}
    ids_por_nombre_clase: dict[str, str] = {}
    for node in nodes:
        ids_por_nombre_clase.setdefault(node["data"]["nombre"].strip(), node["id"])

    def id_tipo(nombre_tipo: str) -> str:
        # Un tipo que es una clase del diagrama referencia la clase, no un PrimitiveType.
        if nombre_tipo.strip() in ids_por_nombre_clase:
            return ids_por_nombre_clase[nombre_tipo.strip()]
        if nombre_tipo not in tipos_primitivos:
            tipos_primitivos[nombre_tipo] = f"tipo-{_slug(nombre_tipo)}"
        return tipos_primitivos[nombre_tipo]

    # clase de asociación (id de nodo) -> la relación de la que cuelga.
    # validar_contenido ya garantiza que cada clase se usa en una sola relación.
    relacion_de_clase_asociacion = {
        e["data"]["claseAsociacion"]: e for e in edges if e["data"].get("claseAsociacion")
    }

    elementos_clase: dict[str, ET.Element] = {}
    for node in nodes:
        clase = ET.SubElement(modelo, "packagedElement")
        es_clase_asociacion = node["id"] in relacion_de_clase_asociacion
        clase.set(XMI_TYPE, "uml:AssociationClass" if es_clase_asociacion else "uml:Class")
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
                _agregar_ref_tipo(attr_elem, id_tipo(atributo["tipo"]))

        for metodo in node["data"]["metodos"]:
            # name = solo el nombre: con la firma completa EA muestra
            # "anular(): void()" porque le agrega su propio "()".
            nombre, parametros, retorno = _firma_de_metodo(metodo)
            op_elem = ET.SubElement(clase, "ownedOperation")
            op_elem.set(XMI_TYPE, "uml:Operation")
            op_elem.set(XMI_ID, metodo["id"])
            op_elem.set("name", nombre)
            op_elem.set("visibility", _VISIBILIDAD_A_UML[metodo["visibilidad"]])
            for pos, (nombre_param, tipo_param) in enumerate(parametros):
                param_elem = ET.SubElement(op_elem, "ownedParameter")
                param_elem.set(XMI_TYPE, "uml:Parameter")
                param_elem.set(XMI_ID, f"{metodo['id']}-p{pos}")
                param_elem.set("name", nombre_param)
                param_elem.set("direction", "in")
                if tipo_param:
                    _agregar_ref_tipo(param_elem, id_tipo(tipo_param))
            if retorno:
                ret_elem = ET.SubElement(op_elem, "ownedParameter")
                ret_elem.set(XMI_TYPE, "uml:Parameter")
                ret_elem.set(XMI_ID, f"{metodo['id']}-ret")
                ret_elem.set("name", "return")
                ret_elem.set("direction", "return")
                _agregar_ref_tipo(ret_elem, id_tipo(retorno))

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

        if data.get("claseAsociacion"):
            # La AssociationClass es a la vez la clase y la asociación: sus
            # extremos van dentro del mismo elemento (el nombre ya es el de la
            # clase, así que el nombre de la relación no viaja).
            _agregar_extremos(elementos_clase[data["claseAsociacion"]], edge)
            continue

        assoc_elem = ET.SubElement(modelo, "packagedElement")
        assoc_elem.set(XMI_TYPE, "uml:Association")
        assoc_elem.set(XMI_ID, edge["id"])
        if data["nombre"]:
            assoc_elem.set("name", data["nombre"])
        _agregar_extremos(assoc_elem, edge)

    _agregar_extension_ea(xmi, nodes, set(relacion_de_clase_asociacion))

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
    # Los tipos que son clases del diagrama referencian el xmi:id de la clase.
    for elem in modelo.findall("packagedElement"):
        if elem.get(XMI_TYPE) in ("uml:Class", "uml:AssociationClass") and elem.get(XMI_ID) and elem.get("name"):
            tipos_primitivos.setdefault(elem.get(XMI_ID), elem.get("name"))

    extension = xmi.find(f"{{{NS_XMI}}}Extension")
    tipos_atributos_ea, operaciones_ea = _indice_extension_ea(extension)

    nodes = []
    ids_nodos = set()
    generalizaciones = []  # (edge_id, origen_id, destino_id)
    for elem in modelo.findall("packagedElement"):
        if elem.get(XMI_TYPE) not in ("uml:Class", "uml:AssociationClass"):
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
                    "tipo": _nombre_tipo(
                        _ref_tipo(attr_elem), tipos_primitivos, tipos_atributos_ea.get(attr_elem.get(XMI_ID))
                    ),
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
                    "texto": _texto_de_operacion(op_elem, tipos_primitivos, operaciones_ea),
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

        if tipo_xmi not in ("uml:Association", "uml:AssociationClass"):
            continue

        extremos = elem.findall("ownedEnd")
        if len(extremos) != 2:
            raise ArchivoInvalidoError(f'La asociación "{elem.get(XMI_ID)}" no tiene dos extremos.')

        if tipo_xmi == "uml:AssociationClass":
            # Una sola pieza en XMI, dos en el diagrama: el nodo (ya creado en el
            # loop de clases) y la relación, que lo referencia como claseAsociacion.
            # El id de la relación se recupera del id del extremo ("<rel>-origen").
            id_extremo = extremos[0].get(XMI_ID) or ""
            edge_id = id_extremo.removesuffix("-origen") if id_extremo.endswith("-origen") else None
            agregar_edge(
                edge_id or f"{elem.get(XMI_ID)}-asociacion",
                _ref_tipo(extremos[0]),
                _ref_tipo(extremos[1]),
                {
                    "tipo": "asociacion",
                    "multiplicidadOrigen": _leer_multiplicidad(extremos[0]),
                    "multiplicidadDestino": _leer_multiplicidad(extremos[1]),
                    "nombre": None,
                    "estiloLinea": "recta",
                    "claseAsociacion": elem.get(XMI_ID),
                },
            )
            continue

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
            _ref_tipo(extremo_origen),
            _ref_tipo(extremo_destino),
            {
                "tipo": tipo,
                "multiplicidadOrigen": _leer_multiplicidad(extremo_origen),
                "multiplicidadDestino": _leer_multiplicidad(extremo_destino),
                "nombre": elem.get("name"),
                "estiloLinea": "recta",
            },
        )

    if not nodes:
        if extension is not None:
            nombres_parametros = {
                p.get(XMI_ID): p.get("name") for p in xmi.iter("ownedParameter") if p.get(XMI_ID) and p.get("name")
            }
            resultado_ea = _contenido_desde_extension_ea(extension, nombres_parametros)
            if resultado_ea is not None:
                return resultado_ea

    return validar_contenido({"nodes": nodes, "edges": edges})
