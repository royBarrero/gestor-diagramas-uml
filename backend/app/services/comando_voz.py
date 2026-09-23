"""Integración con OpenAI para CU08: transcripción de audio e interpretación
de comandos de voz para generar una o más acciones estructuradas sobre el
diagrama de clases. Aislado acá para que el resto del backend no dependa de
que la API key esté configurada ni del SDK de OpenAI.
"""

import json
import uuid

from app.services.constantes_diagrama import TIPOS_RELACION, VISIBILIDADES, normalizar
from app.services.ia_cliente import ServicioIANoDisponibleError, cliente_openai

# gpt-4o-transcribe entiende mejor el español y respeta el vocabulario del
# `prompt`; whisper-1 queda como respaldo si la key no tiene acceso al primero.
MODELO_TRANSCRIPCION = "gpt-4o-transcribe"
MODELO_TRANSCRIPCION_RESPALDO = "whisper-1"
# gpt-4o-mini se perdía con comandos de varias órdenes en un mismo audio.
MODELO_INTERPRETACION = "gpt-4.1"

_VOCABULARIO_UML = (
    "Diagrama de clases UML. Clase, atributo, método, relación, asociación, herencia, "
    "agregación, composición, dependencia, clase intermedia, clase de asociación, "
    "multiplicidad, uno, muchos, asterisco, cero punto punto uno, uno punto punto asterisco, "
    "público, privado, protegido, String, int, float, double, boolean, Date."
)


class ComandoNoInterpretadoError(Exception):
    """El comando es ambiguo, no describe una acción soportada, o referencia
    una clase que no existe en el diagrama."""


def _prompt_transcripcion(contenido: dict | None) -> str:
    """Vocabulario de ayuda para la transcripción: términos UML + los nombres
    de clases y atributos del diagrama actual, para que no los escriba mal
    (ej. "benta" en vez de "Venta")."""
    nombres = []
    for nodo in (contenido or {}).get("nodes", []):
        data = nodo.get("data", {})
        nombres.append(data.get("nombre") or "")
        nombres.extend(item.get("texto") or "" for item in data.get("atributos") or [])
    nombres = [n for n in dict.fromkeys(nombres) if n]
    if not nombres:
        return _VOCABULARIO_UML
    return f"{_VOCABULARIO_UML} Nombres usados en este diagrama: {', '.join(nombres)}."


def transcribir_audio(audio_bytes: bytes, nombre_archivo: str, contenido: dict | None = None) -> str:
    cliente = cliente_openai()
    prompt = _prompt_transcripcion(contenido)
    ultimo_error = None
    for modelo in (MODELO_TRANSCRIPCION, MODELO_TRANSCRIPCION_RESPALDO):
        try:
            resultado = cliente.audio.transcriptions.create(
                model=modelo,
                file=(nombre_archivo, audio_bytes),
                language="es",
                prompt=prompt,
            )
            return resultado.text
        except Exception as exc:  # cualquier falla de red/API se trata como "IA no disponible"
            ultimo_error = exc
    raise ServicioIANoDisponibleError("No se pudo contactar al servicio de voz.") from ultimo_error


_ACCION_SCHEMA = {
    "type": "object",
    "properties": {
        "accion": {
            "type": "string",
            "enum": [
                "crear_clase",
                "agregar_atributo",
                "agregar_metodo",
                "eliminar_atributo",
                "eliminar_metodo",
                "editar_atributo",
                "editar_metodo",
                "crear_relacion",
                "asignar_clase_asociacion",
                "quitar_clase_asociacion",
                "eliminar_clase",
                "eliminar_relacion",
                "no_entendido",
            ],
        },
        "clase": {
            "type": ["string", "null"],
            "description": "Nombre de la clase a crear, o de la clase existente destino.",
        },
        "elemento_objetivo": {
            "type": ["string", "null"],
            "description": (
                "Nombre ACTUAL del atributo o método a eliminar o editar. Solo se usa con "
                "eliminar_atributo, eliminar_metodo, editar_atributo o editar_metodo."
            ),
        },
        "atributos": {
            "type": "array",
            "description": (
                "Para crear_clase/agregar_atributo: los atributos a agregar. Para "
                "editar_atributo: un único elemento con el nuevo nombre, tipo y visibilidad."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "nombre": {"type": "string"},
                    "tipo": {
                        "type": ["string", "null"],
                        "description": (
                            "Tipo de dato del atributo si el comando lo menciona (ej. 'String', "
                            "'int', 'boolean'). null si no se menciona un tipo de dato."
                        ),
                    },
                    "visibilidad": {"type": "string", "enum": list(VISIBILIDADES)},
                },
                "required": ["nombre", "tipo", "visibilidad"],
                "additionalProperties": False,
            },
        },
        "metodos": {
            "type": "array",
            "description": (
                "Para crear_clase/agregar_metodo: los métodos a agregar. Para "
                "editar_metodo: un único elemento con el nuevo nombre y visibilidad."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "nombre": {"type": "string"},
                    "visibilidad": {"type": "string", "enum": list(VISIBILIDADES)},
                },
                "required": ["nombre", "visibilidad"],
                "additionalProperties": False,
            },
        },
        "relacion": {
            "type": ["object", "null"],
            "description": (
                "Para crear_relacion, asignar_clase_asociacion, quitar_clase_asociacion y "
                "eliminar_relacion."
            ),
            "properties": {
                "claseOrigen": {"type": "string"},
                "claseDestino": {"type": "string"},
                "tipo": {
                    "type": ["string", "null"],
                    "enum": [*TIPOS_RELACION, None],
                    "description": (
                        "Tipo de relación. En eliminar_relacion, null si el comando no dice el "
                        "tipo. En crear_relacion, null equivale a 'asociacion'."
                    ),
                },
                "multiplicidadOrigen": {
                    "type": ["string", "null"],
                    "description": "La multiplicidad dicha para claseOrigen (no la de claseDestino).",
                },
                "multiplicidadDestino": {
                    "type": ["string", "null"],
                    "description": "La multiplicidad dicha para claseDestino (no la de claseOrigen).",
                },
                "nombre": {"type": ["string", "null"]},
                "claseAsociacion": {
                    "type": ["string", "null"],
                    "description": (
                        "Clase intermedia / clase de asociación de esta asociación (típica de "
                        "relaciones muchos a muchos). null si no se pide ninguna."
                    ),
                },
            },
            "required": [
                "claseOrigen",
                "claseDestino",
                "tipo",
                "multiplicidadOrigen",
                "multiplicidadDestino",
                "nombre",
                "claseAsociacion",
            ],
            "additionalProperties": False,
        },
        "motivo_no_entendido": {"type": ["string", "null"]},
    },
    "required": [
        "accion",
        "clase",
        "elemento_objetivo",
        "atributos",
        "metodos",
        "relacion",
        "motivo_no_entendido",
    ],
    "additionalProperties": False,
}

ACCIONES_JSON_SCHEMA = {
    "name": "acciones_diagrama",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "acciones": {
                "type": "array",
                "description": (
                    "Todas las acciones pedidas en el comando, en el orden en que hay que "
                    "aplicarlas (primero las clases, después las relaciones que las usan)."
                ),
                "items": _ACCION_SCHEMA,
            },
        },
        "required": ["acciones"],
        "additionalProperties": False,
    },
}

_PROMPT_SISTEMA = (
    "Interpretás comandos de voz en español para editar un diagrama UML de clases. El texto "
    "viene de una transcripción automática de audio, así que puede tener errores de oído. Tu "
    "respuesta debe cumplir siempre el schema JSON dado.\n\n"
    "Un mismo comando puede pedir VARIAS cosas (ej. 'creá la clase Cliente con id y nombre, la "
    "clase Venta con id y fecha, y una relación de 1 en Cliente y muchos en Venta'). Devolvé en "
    "'acciones' UNA acción por cada cosa pedida, en orden: primero las clases, después sus "
    "atributos/métodos extra y al final las relaciones. No omitas ninguna parte del comando.\n\n"
    "Acciones posibles:\n"
    "- crear_clase: una clase nueva, opcionalmente con atributos y/o métodos.\n"
    "- agregar_atributo / agregar_metodo: a una clase indicada en 'clase'.\n"
    "- eliminar_atributo / eliminar_metodo: borra de 'clase' el atributo/método cuyo nombre "
    "ACTUAL va en 'elemento_objetivo'.\n"
    "- editar_atributo / editar_metodo: renombra y/o cambia visibilidad o tipo: "
    "'elemento_objetivo' lleva su nombre actual, y 'atributos'/'metodos' un único elemento con los "
    "valores nuevos; lo que el comando no mencione se conserva con el valor actual del diagrama.\n"
    "- crear_relacion: entre dos clases, con un tipo de relación UML.\n"
    "- asignar_clase_asociacion: convierte una clase en la clase intermedia (clase de asociación) "
    "de una asociación que YA existe entre claseOrigen y claseDestino; va en "
    "'relacion.claseAsociacion'. El resto de los campos de 'relacion' se completan con los de la "
    "relación existente.\n"
    "- quitar_clase_asociacion: la asociación entre claseOrigen y claseDestino deja de tener clase "
    "intermedia; la clase y la asociación se conservan (ej. 'quitá la clase intermedia de Venta y "
    "Producto').\n"
    "- eliminar_clase: borra la clase indicada en 'clase' (ej. 'eliminá la clase Vendedor'). Eso "
    "ya borra todas sus relaciones: NO agregues eliminar_relacion extra para ellas.\n"
    "- eliminar_relacion: borra la relación entre claseOrigen y claseDestino (en cualquier orden). "
    "Si el comando nombra el tipo ('borrá la herencia entre Alumno y Persona') ponelo en "
    "'relacion.tipo'; si solo dice 'la relación', tipo=null.\n"
    "- no_entendido: para una parte del comando que no corresponde a ninguna acción, es ambigua o "
    "le faltan datos imprescindibles; explicá el motivo en 'motivo_no_entendido'.\n\n"
    "Clases existentes: las del estado del diagrama que se te da, MÁS las creadas antes en este "
    "mismo comando (una relación puede usar una clase que se crea en una acción anterior). Si una "
    "clase de un agregar/eliminar/editar/relación no está en ninguno de esos dos grupos, esa parte "
    "es no_entendido — NUNCA agregues un crear_clase que el comando no pidió explícitamente "
    "('creá', 'agregá la clase', 'nueva clase'...) solo para poder armar una relación. Ejemplo: "
    "'relacioná Factura con Venta' cuando Factura no existe en el diagrama ni se creó antes en "
    "este comando -> esa parte es no_entendido (motivo: no existe la clase Factura), NO un "
    "crear_clase Factura. Si el texto dice un nombre parecido a una clase o atributo existente "
    "(ej. 'benta' y existe 'Venta'), es un error de transcripción: usá el nombre existente, "
    "escrito exactamente igual.\n\n"
    "Nombres: clases en PascalCase ('detalle venta' -> 'DetalleVenta'), atributos y métodos en "
    "camelCase con minúscula inicial ('precio unitario' -> 'precioUnitario'). Visibilidad "
    "'publico' salvo que se diga otra. Tipo de dato de un atributo solo si el comando lo menciona "
    "(ej. 'nombre de tipo String'); si no, tipo=null.\n\n"
    "Multiplicidades dichas en voz alta: 'uno' -> '1'; 'muchos', 'varios', 'asterisco', "
    "'estrella', 'n' -> '*'; 'cero o uno', 'cero punto punto uno' -> '0..1'; 'uno o más', 'uno o "
    "muchos', 'uno punto punto asterisco' -> '1..*'; 'cero o muchos' -> '0..*'. Cada multiplicidad "
    "va con la clase junto a la que se la nombra: 'relación de 1 en Cliente y muchos en Venta' "
    "con claseOrigen='Cliente', claseDestino='Venta' -> multiplicidadOrigen='1', "
    "multiplicidadDestino='*'. 'Un cliente tiene muchas ventas' -> Cliente '1', Venta '*'. "
    "'Muchos a muchos entre A y B' -> '*' en ambos extremos. Si no se dice ninguna "
    "multiplicidad, null. Si se dice 'relación' sin especificar tipo, es 'asociacion'. Para "
    "herencia ('B hereda de A', 'B es un A'): claseOrigen=B (subclase), claseDestino=A, sin "
    "multiplicidades. Para composición/agregación: claseOrigen es el todo, claseDestino la parte.\n\n"
    "Clase intermedia (clase de asociación): 'X es la clase intermedia entre A y B', 'X como "
    "clase de asociación de A y B', 'A y B muchos a muchos con la clase intermedia X' -> si la "
    "clase X no existe, primero crear_clase X (con los atributos que se digan); después, si NO "
    "existe una asociación entre A y B, crear_relacion A-B de tipo 'asociacion' con "
    "claseAsociacion='X' (si no se dicen multiplicidades, '*' en ambos extremos); si ya existe, "
    "asignar_clase_asociacion. NUNCA la representes como relaciones separadas entre X y A o X y "
    "B.\n\n"
    "Completá siempre todos los campos del schema, usando null o listas vacías cuando no apliquen."
)


def _describir_nodes(nodes: list[dict]) -> str:
    def _listar(items: list[dict]) -> str:
        return ", ".join(f'{i.get("texto")} ({i.get("visibilidad")})' for i in items) or "(ninguno)"

    lineas = [
        f'- {n.get("data", {}).get("nombre")}: '
        f'atributos: {_listar(n.get("data", {}).get("atributos") or [])}; '
        f'métodos: {_listar(n.get("data", {}).get("metodos") or [])}'
        for n in nodes
    ]
    return "\n".join(lineas) or "(ninguna todavía)"


def _describir_edges(nodes: list[dict], edges: list[dict]) -> str:
    nombres = {n.get("id"): n.get("data", {}).get("nombre") for n in nodes}
    lineas = []
    for e in edges:
        data = e.get("data", {})
        linea = (
            f'- {nombres.get(e.get("source"))} [{data.get("multiplicidadOrigen") or "-"}] '
            f'--{data.get("tipo")}-- {nombres.get(e.get("target"))} '
            f'[{data.get("multiplicidadDestino") or "-"}]'
        )
        if nombres.get(data.get("claseAsociacion")):
            linea += f' (clase de asociación: {nombres[data["claseAsociacion"]]})'
        lineas.append(linea)
    return "\n".join(lineas) or "(ninguna todavía)"


def interpretar_comando(texto: str, contenido: dict) -> dict:
    """Devuelve un dict que cumple ACCIONES_JSON_SCHEMA: {"acciones": [...]}.

    `contenido` es el estado actual del diagrama (clases con sus atributos y
    métodos, y relaciones), usado como contexto para resolver a qué se refiere
    el comando y para poder conservar valores no mencionados al editar.

    Lanza ServicioIANoDisponibleError si falla la llamada a OpenAI.
    """
    cliente = cliente_openai()
    nodes, edges = contenido.get("nodes", []), contenido.get("edges", [])
    contexto = (
        f"Estado actual del diagrama.\nClases:\n{_describir_nodes(nodes)}\n\n"
        f"Relaciones:\n{_describir_edges(nodes, edges)}"
    )
    try:
        respuesta = cliente.chat.completions.create(
            model=MODELO_INTERPRETACION,
            temperature=0,
            messages=[
                {"role": "system", "content": _PROMPT_SISTEMA},
                {"role": "system", "content": contexto},
                {"role": "user", "content": texto},
            ],
            response_format={"type": "json_schema", "json_schema": ACCIONES_JSON_SCHEMA},
        )
        return json.loads(respuesta.choices[0].message.content)
    except ServicioIANoDisponibleError:
        raise
    except Exception as exc:
        raise ServicioIANoDisponibleError(
            "No se pudo interpretar el comando (servicio de IA no disponible)."
        ) from exc


def _generar_id(prefijo: str) -> str:
    return f"{prefijo}-{uuid.uuid4().hex[:10]}"


def _buscar_clase(nodes: list[dict], nombre: str | None) -> dict | None:
    nombre_normalizado = normalizar(nombre)
    if not nombre_normalizado:
        return None
    return next(
        (n for n in nodes if normalizar(n.get("data", {}).get("nombre")) == nombre_normalizado),
        None,
    )


def _items(lista: list[dict] | None, prefijo: str) -> list[dict]:
    return [
        {
            "id": _generar_id(prefijo),
            "visibilidad": item["visibilidad"],
            "tipo": item.get("tipo") or "",
            "texto": item["nombre"],
        }
        for item in (lista or [])
    ]


def _buscar_item_por_texto(items: list[dict], nombre: str | None) -> dict | None:
    nombre_normalizado = normalizar(nombre)
    if not nombre_normalizado:
        return None
    return next(
        (item for item in items if normalizar(item.get("texto")) == nombre_normalizado),
        None,
    )


_COLUMNAS_GRILLA = 4
_ANCHO_CELDA = 280
_ALTO_CELDA = 260


def _posicion_nueva_clase(nodes: list[dict]) -> dict:
    """Primera celda libre de una grilla de 4 columnas, para que varias clases
    creadas en un mismo comando no queden encimadas entre sí ni sobre las que
    ya estaban (una celda está ocupada si hay una clase a menos de una celda
    de distancia)."""
    posiciones = [n.get("position", {}) for n in nodes]
    celda = 0
    while True:
        x = 120 + (celda % _COLUMNAS_GRILLA) * _ANCHO_CELDA
        y = 120 + (celda // _COLUMNAS_GRILLA) * _ALTO_CELDA
        if all(
            abs(p.get("x", 0) - x) >= _ANCHO_CELDA or abs(p.get("y", 0) - y) >= _ALTO_CELDA
            for p in posiciones
        ):
            return {"x": x, "y": y}
        celda += 1


def _clase_de_asociacion_valida(edges: list[dict], edge: dict, nodo: dict | None, nombre: str | None) -> str:
    """Mismas reglas que el editor (EditarRelacionModal.jsx) y validar_contenido:
    solo en asociaciones, no uno de los extremos, y no usada en otra relación.
    Devuelve el id del nodo o lanza ComandoNoInterpretadoError."""
    if nodo is None:
        raise ComandoNoInterpretadoError(f'No encontré ninguna clase llamada "{nombre}".')
    nombre = nodo["data"]["nombre"]
    if edge["data"].get("tipo") != "asociacion":
        raise ComandoNoInterpretadoError("Solo una asociación puede tener clase intermedia.")
    if nodo["id"] in (edge["source"], edge["target"]):
        raise ComandoNoInterpretadoError(f'"{nombre}" no puede ser clase intermedia de su propia relación.')
    if any(e is not edge and e.get("data", {}).get("claseAsociacion") == nodo["id"] for e in edges):
        raise ComandoNoInterpretadoError(f'"{nombre}" ya es la clase intermedia de otra relación.')
    return nodo["id"]


_ETIQUETA_TIPO = {
    "asociacion": "asociación",
    "herencia": "herencia",
    "agregacion": "agregación",
    "composicion": "composición",
    "dependencia": "dependencia",
}


def _indice_relacion(nodes: list[dict], edges: list[dict], rel: dict, tipo: str | None) -> int:
    """Índice en `edges` de la única relación entre claseOrigen y claseDestino
    (en cualquier dirección), filtrando por `tipo` si se indica. Lanza
    ComandoNoInterpretadoError si no hay ninguna, o si hay varias y no se
    dijo el tipo para desambiguar."""
    a = _buscar_clase(nodes, rel.get("claseOrigen"))
    b = _buscar_clase(nodes, rel.get("claseDestino"))
    if a is None or b is None:
        faltante = rel.get("claseOrigen") if a is None else rel.get("claseDestino")
        raise ComandoNoInterpretadoError(f'No encontré ninguna clase llamada "{faltante}".')
    nombre_a, nombre_b = a["data"]["nombre"], b["data"]["nombre"]
    extremos = {a["id"], b["id"]}
    indices = [
        i
        for i, e in enumerate(edges)
        if {e["source"], e["target"]} == extremos and (tipo is None or e.get("data", {}).get("tipo") == tipo)
    ]
    if not indices:
        detalle = f"de tipo {_ETIQUETA_TIPO.get(tipo, tipo)} " if tipo else ""
        raise ComandoNoInterpretadoError(f'No hay ninguna relación {detalle}entre "{nombre_a}" y "{nombre_b}".')
    if len(indices) > 1:
        tipos = ", ".join(_ETIQUETA_TIPO.get(edges[i]["data"].get("tipo"), "?") for i in indices)
        raise ComandoNoInterpretadoError(
            f'Hay varias relaciones entre "{nombre_a}" y "{nombre_b}" ({tipos}); decí de qué tipo es.'
        )
    return indices[0]


def aplicar_accion(contenido: dict, accion: dict) -> dict:
    """Función pura: no toca la DB. Devuelve un nuevo dict {"nodes", "edges"}.

    Lanza ComandoNoInterpretadoError si la acción no se puede aplicar.
    """
    nodes = [dict(n) for n in contenido.get("nodes", [])]
    edges = [dict(e) for e in contenido.get("edges", [])]
    tipo_accion = accion.get("accion")

    if tipo_accion == "crear_clase":
        nombre = accion.get("clase") or "NuevaClase"
        if _buscar_clase(nodes, nombre) is not None:
            raise ComandoNoInterpretadoError(f'Ya existe una clase llamada "{nombre}".')
        nuevo_nodo = {
            "id": _generar_id("clase"),
            "type": "clase",
            "position": _posicion_nueva_clase(nodes),
            "data": {
                "nombre": nombre,
                "atributos": _items(accion.get("atributos"), "atributos"),
                "metodos": _items(accion.get("metodos"), "metodos"),
            },
        }
        nodes.append(nuevo_nodo)

    elif tipo_accion in ("agregar_atributo", "agregar_metodo"):
        nodo = _buscar_clase(nodes, accion.get("clase"))
        if nodo is None:
            raise ComandoNoInterpretadoError(f'No encontré ninguna clase llamada "{accion.get("clase")}".')
        campo = "atributos" if tipo_accion == "agregar_atributo" else "metodos"
        items = accion.get(campo) or []
        if not items:
            raise ComandoNoInterpretadoError("No entendí qué atributo o método agregar.")
        nodo["data"] = {**nodo["data"], campo: [*nodo["data"][campo], *_items(items, campo)]}

    elif tipo_accion in ("eliminar_atributo", "eliminar_metodo"):
        nodo = _buscar_clase(nodes, accion.get("clase"))
        if nodo is None:
            raise ComandoNoInterpretadoError(f'No encontré ninguna clase llamada "{accion.get("clase")}".')
        campo = "atributos" if tipo_accion == "eliminar_atributo" else "metodos"
        etiqueta = "atributo" if tipo_accion == "eliminar_atributo" else "método"
        objetivo = _buscar_item_por_texto(nodo["data"][campo], accion.get("elemento_objetivo"))
        if objetivo is None:
            raise ComandoNoInterpretadoError(
                f'La clase "{nodo["data"]["nombre"]}" no tiene ningún {etiqueta} '
                f'llamado "{accion.get("elemento_objetivo")}".'
            )
        nodo["data"] = {
            **nodo["data"],
            campo: [item for item in nodo["data"][campo] if item["id"] != objetivo["id"]],
        }

    elif tipo_accion in ("editar_atributo", "editar_metodo"):
        nodo = _buscar_clase(nodes, accion.get("clase"))
        if nodo is None:
            raise ComandoNoInterpretadoError(f'No encontré ninguna clase llamada "{accion.get("clase")}".')
        campo = "atributos" if tipo_accion == "editar_atributo" else "metodos"
        etiqueta = "atributo" if tipo_accion == "editar_atributo" else "método"
        objetivo = _buscar_item_por_texto(nodo["data"][campo], accion.get("elemento_objetivo"))
        if objetivo is None:
            raise ComandoNoInterpretadoError(
                f'La clase "{nodo["data"]["nombre"]}" no tiene ningún {etiqueta} '
                f'llamado "{accion.get("elemento_objetivo")}".'
            )
        nueva_definicion = (accion.get(campo) or [None])[0]
        if not nueva_definicion:
            raise ComandoNoInterpretadoError("No entendí cuál es el nuevo nombre o visibilidad.")
        cambios = {"texto": nueva_definicion["nombre"], "visibilidad": nueva_definicion["visibilidad"]}
        if campo == "atributos":
            nuevo_tipo = nueva_definicion.get("tipo")
            cambios["tipo"] = nuevo_tipo if nuevo_tipo is not None else objetivo.get("tipo", "")
        nodo["data"] = {
            **nodo["data"],
            campo: [
                {**objetivo, **cambios} if item["id"] == objetivo["id"] else item
                for item in nodo["data"][campo]
            ],
        }

    elif tipo_accion == "crear_relacion":
        rel = accion.get("relacion") or {}
        origen = _buscar_clase(nodes, rel.get("claseOrigen"))
        destino = _buscar_clase(nodes, rel.get("claseDestino"))
        if origen is None or destino is None:
            faltante = rel.get("claseOrigen") if origen is None else rel.get("claseDestino")
            raise ComandoNoInterpretadoError(f'No encontré ninguna clase llamada "{faltante}".')
        nuevo_edge = {
            "id": _generar_id("rel"),
            "source": origen["id"],
            "target": destino["id"],
            "type": "relacion",
            "data": {
                "tipo": rel.get("tipo") or "asociacion",
                "multiplicidadOrigen": rel.get("multiplicidadOrigen"),
                "multiplicidadDestino": rel.get("multiplicidadDestino"),
                "nombre": rel.get("nombre"),
                "estiloLinea": "recta",
            },
        }
        if rel.get("claseAsociacion"):
            nodo_asociacion = _buscar_clase(nodes, rel["claseAsociacion"])
            nuevo_edge["data"]["claseAsociacion"] = _clase_de_asociacion_valida(
                edges, nuevo_edge, nodo_asociacion, rel["claseAsociacion"]
            )
        edges.append(nuevo_edge)

    elif tipo_accion == "asignar_clase_asociacion":
        rel = accion.get("relacion") or {}
        a = _buscar_clase(nodes, rel.get("claseOrigen"))
        b = _buscar_clase(nodes, rel.get("claseDestino"))
        sin_asociacion = (
            a is not None
            and b is not None
            and not any(
                {e["source"], e["target"]} == {a["id"], b["id"]} and e.get("data", {}).get("tipo") == "asociacion"
                for e in edges
            )
        )
        if sin_asociacion:
            # El modelo a veces elige asignar cuando la asociación todavía no
            # existe ("clase intermedia entre A y B" con A y B sin relacionar):
            # la intención es clara, así que se crea la asociación muchos a muchos.
            relacion_nueva = {
                **rel,
                "tipo": "asociacion",
                "multiplicidadOrigen": rel.get("multiplicidadOrigen") or "*",
                "multiplicidadDestino": rel.get("multiplicidadDestino") or "*",
            }
            return aplicar_accion(
                {"nodes": nodes, "edges": edges}, {"accion": "crear_relacion", "relacion": relacion_nueva}
            )
        indice = _indice_relacion(nodes, edges, rel, "asociacion")
        edge = edges[indice]
        nodo_asociacion = _buscar_clase(nodes, rel.get("claseAsociacion"))
        clase_id = _clase_de_asociacion_valida(edges, edge, nodo_asociacion, rel.get("claseAsociacion"))
        edges[indice] = {**edge, "data": {**edge["data"], "claseAsociacion": clase_id}}

    elif tipo_accion == "quitar_clase_asociacion":
        indice = _indice_relacion(nodes, edges, accion.get("relacion") or {}, "asociacion")
        edge = edges[indice]
        if not edge["data"].get("claseAsociacion"):
            raise ComandoNoInterpretadoError("Esa asociación no tiene clase intermedia.")
        edges[indice] = {**edge, "data": {**edge["data"], "claseAsociacion": None}}

    elif tipo_accion == "eliminar_clase":
        nodo = _buscar_clase(nodes, accion.get("clase"))
        if nodo is None:
            raise ComandoNoInterpretadoError(f'No encontré ninguna clase llamada "{accion.get("clase")}".')
        # Igual que eliminarClase + quitarClasesAsociacion en PizarraContext.jsx:
        # se van sus relaciones, y si era clase intermedia de otra relación, esa
        # relación queda pero sin la referencia.
        nodes = [n for n in nodes if n["id"] != nodo["id"]]
        edges = [
            {**e, "data": {**e["data"], "claseAsociacion": None}}
            if e.get("data", {}).get("claseAsociacion") == nodo["id"]
            else e
            for e in edges
            if nodo["id"] not in (e["source"], e["target"])
        ]

    elif tipo_accion == "eliminar_relacion":
        rel = accion.get("relacion") or {}
        indice = _indice_relacion(nodes, edges, rel, rel.get("tipo"))
        # Si tenía clase intermedia, la clase queda suelta (no se borra), como en el editor.
        edges.pop(indice)

    else:
        raise ComandoNoInterpretadoError(accion.get("motivo_no_entendido") or "No entendí el comando.")

    return {"nodes": nodes, "edges": edges}


def aplicar_acciones(contenido: dict, resultado: dict) -> tuple[dict, int, list[str]]:
    """Aplica en orden todas las acciones de `resultado` (ver
    ACCIONES_JSON_SCHEMA), cada una sobre el contenido que dejó la anterior —
    así una relación puede usar una clase creada en el mismo comando.

    Una acción que falla no frena a las demás: se saltea y su motivo se
    devuelve en `errores`. Devuelve `(nuevo_contenido, aplicadas, errores)`.
    """
    aplicadas, errores = 0, []
    for accion in resultado.get("acciones") or []:
        try:
            contenido = aplicar_accion(contenido, accion)
            aplicadas += 1
        except ComandoNoInterpretadoError as exc:
            errores.append(str(exc))
    if aplicadas == 0 and not errores:
        errores.append("No entendí el comando.")
    return contenido, aplicadas, errores
