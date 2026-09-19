"""Integración con OpenAI para CU08: transcripción de audio (Whisper) e
interpretación de comandos de voz para generar una acción estructurada sobre
el diagrama de clases. Aislado acá para que el resto del backend no dependa
de que la API key esté configurada ni del SDK de OpenAI.
"""

import json
import uuid

from app.services.constantes_diagrama import TIPOS_RELACION, VISIBILIDADES, normalizar
from app.services.ia_cliente import ServicioIANoDisponibleError, cliente_openai

MODELO_TRANSCRIPCION = "whisper-1"
MODELO_INTERPRETACION = "gpt-4o-mini"


class ComandoNoInterpretadoError(Exception):
    """El comando es ambiguo, no describe una acción soportada, o referencia
    una clase que no existe en el diagrama."""


def transcribir_audio(audio_bytes: bytes, nombre_archivo: str) -> str:
    cliente = cliente_openai()
    try:
        resultado = cliente.audio.transcriptions.create(
            model=MODELO_TRANSCRIPCION,
            file=(nombre_archivo, audio_bytes),
        )
    except Exception as exc:  # cualquier falla de red/API se trata como "IA no disponible"
        raise ServicioIANoDisponibleError("No se pudo contactar al servicio de voz.") from exc
    return resultado.text


ACCION_JSON_SCHEMA = {
    "name": "accion_diagrama",
    "strict": True,
    "schema": {
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
                "properties": {
                    "claseOrigen": {"type": "string"},
                    "claseDestino": {"type": "string"},
                    "tipo": {"type": "string", "enum": list(TIPOS_RELACION)},
                    "multiplicidadOrigen": {"type": ["string", "null"]},
                    "multiplicidadDestino": {"type": ["string", "null"]},
                    "nombre": {"type": ["string", "null"]},
                },
                "required": [
                    "claseOrigen",
                    "claseDestino",
                    "tipo",
                    "multiplicidadOrigen",
                    "multiplicidadDestino",
                    "nombre",
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
    },
}

_PROMPT_SISTEMA = (
    "Interpretás comandos de voz en español para editar un diagrama UML de clases. "
    "Tu respuesta debe cumplir siempre el schema JSON dado. Las acciones posibles son: "
    "crear_clase (una clase nueva, opcionalmente con atributos y/o métodos), "
    "agregar_atributo o agregar_metodo (a una clase EXISTENTE, indicada en 'clase'), "
    "eliminar_atributo o eliminar_metodo (borra de una clase EXISTENTE el atributo/método "
    "cuyo nombre ACTUAL va en 'elemento_objetivo'), "
    "editar_atributo o editar_metodo (renombra y/o cambia la visibilidad de un atributo/método "
    "EXISTENTE: 'elemento_objetivo' lleva su nombre actual, y 'atributos'/'metodos' lleva un único "
    "elemento con el nombre y la visibilidad nuevos; si el comando no menciona uno de esos datos, "
    "conservá el valor actual tal como figura en el estado del diagrama que se te da), "
    "en atributos (crear_clase, agregar_atributo, editar_atributo), si el comando menciona un tipo "
    "de dato (ej. 'agregá un atributo de tipo String llamado nombre') extraelo en 'tipo'; si no lo "
    "menciona, o es editar_atributo y no se pide cambiar el tipo, usá tipo=null, "
    "crear_relacion (entre dos clases EXISTENTES, con un tipo de relación UML). "
    "Si el comando no corresponde a ninguna de estas acciones, es ambiguo, le faltan datos "
    "imprescindibles (por ejemplo no queda claro el nombre de la clase o del atributo/método "
    "a modificar), usá accion='no_entendido' y explicá el motivo en 'motivo_no_entendido'. "
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


def interpretar_comando(texto: str, nodes: list[dict]) -> dict:
    """Devuelve un dict que cumple ACCION_JSON_SCHEMA.

    `nodes` es el estado actual de las clases del diagrama (con sus atributos
    y métodos), usado como contexto para resolver a qué clase/atributo/método
    se refiere el comando y para poder conservar valores no mencionados al editar.

    Lanza ServicioIANoDisponibleError si falla la llamada a OpenAI.
    """
    cliente = cliente_openai()
    nombres_clases = [n.get("data", {}).get("nombre") for n in nodes]
    contexto = (
        f"Estado actual del diagrama:\n{_describir_nodes(nodes)}\n\n"
        f"Clases que ya existen: {', '.join(nombres_clases) or '(ninguna todavía)'}. "
        "Si el comando se refiere a una de estas clases, usá exactamente ese nombre (mismo texto) "
        "en 'clase' o en 'relacion.claseOrigen'/'relacion.claseDestino'. Si el comando pide agregar/"
        "eliminar/editar un atributo o método, crear una relación, sobre una clase que no está en esa "
        "lista, o sobre un atributo/método que no figura en el estado del diagrama, usá "
        "accion='no_entendido'."
    )
    try:
        respuesta = cliente.chat.completions.create(
            model=MODELO_INTERPRETACION,
            messages=[
                {"role": "system", "content": _PROMPT_SISTEMA},
                {"role": "system", "content": contexto},
                {"role": "user", "content": texto},
            ],
            response_format={"type": "json_schema", "json_schema": ACCION_JSON_SCHEMA},
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


def aplicar_accion(contenido: dict, accion: dict) -> dict:
    """Función pura: no toca la DB. Devuelve un nuevo dict {"nodes", "edges"}.

    Lanza ComandoNoInterpretadoError si la acción no se puede aplicar.
    """
    nodes = [dict(n) for n in contenido.get("nodes", [])]
    edges = list(contenido.get("edges", []))
    tipo_accion = accion.get("accion")

    if tipo_accion == "crear_clase":
        nuevo_nodo = {
            "id": _generar_id("clase"),
            "type": "clase",
            "position": {"x": 120, "y": 120},
            "data": {
                "nombre": accion.get("clase") or "NuevaClase",
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
        edges.append(
            {
                "id": _generar_id("rel"),
                "source": origen["id"],
                "target": destino["id"],
                "type": "relacion",
                "data": {
                    "tipo": rel.get("tipo"),
                    "multiplicidadOrigen": rel.get("multiplicidadOrigen"),
                    "multiplicidadDestino": rel.get("multiplicidadDestino"),
                    "nombre": rel.get("nombre"),
                    "estiloLinea": "recta",
                },
            }
        )

    else:
        raise ComandoNoInterpretadoError(accion.get("motivo_no_entendido") or "No entendí el comando.")

    return {"nodes": nodes, "edges": edges}
