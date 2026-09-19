"""Integración con OpenAI para CU09: reconocimiento de un diagrama de clases
a partir de una fotografía (visión por computadora) y reconstrucción de esa
estructura como nodos/edges para agregar al diagrama actual.
"""

import base64
import json
import uuid

from app.services.constantes_diagrama import TIPOS_RELACION, VISIBILIDADES, normalizar
from app.services.ia_cliente import ServicioIANoDisponibleError, cliente_openai

MODELO_VISION = "gpt-4o-mini"

DIAGRAMA_JSON_SCHEMA = {
    "name": "diagrama_reconocido",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "confianza": {"type": "string", "enum": ["alta", "media", "baja"]},
            "advertencia": {
                "type": ["string", "null"],
                "description": "Motivo por el que el reconocimiento puede ser incompleto o poco confiable.",
            },
            "clases": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "nombre": {"type": "string"},
                        "atributos": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "tipo": {
                                        "type": ["string", "null"],
                                        "description": (
                                            "El tipo de dato del atributo tal como aparece en la imagen "
                                            "(ej. 'String', 'int', 'Date'), SIN el nombre. null si no hay "
                                            "ningún tipo de dato visible."
                                        ),
                                    },
                                    "texto": {
                                        "type": "string",
                                        "description": "Solo el nombre/identificador del atributo, sin el tipo de dato.",
                                    },
                                    "visibilidad": {"type": "string", "enum": list(VISIBILIDADES)},
                                },
                                "required": ["tipo", "texto", "visibilidad"],
                                "additionalProperties": False,
                            },
                        },
                        "metodos": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "texto": {
                                        "type": "string",
                                        "description": (
                                            "La declaración COMPLETA del método tal como aparece en la "
                                            "imagen, incluyendo parámetros y tipo de retorno si están "
                                            "indicados (ej. 'calcularEdad(): int')."
                                        ),
                                    },
                                    "visibilidad": {"type": "string", "enum": list(VISIBILIDADES)},
                                },
                                "required": ["texto", "visibilidad"],
                                "additionalProperties": False,
                            },
                        },
                    },
                    "required": ["nombre", "atributos", "metodos"],
                    "additionalProperties": False,
                },
            },
            "relaciones": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "claseOrigen": {
                            "type": "string",
                            "description": (
                                "La clase del lado 'origen' de la relación. Para herencia: la subclase "
                                "(de donde sale la línea). Para composición/agregación: la clase del "
                                "lado del rombo (el 'todo'). Para asociación/dependencia: cualquiera de "
                                "las dos, pero su multiplicidad va en multiplicidadOrigen."
                            ),
                        },
                        "claseDestino": {
                            "type": "string",
                            "description": (
                                "La clase del lado 'destino' de la relación. Para herencia: la "
                                "superclase (donde está el triángulo). Para composición/agregación: la "
                                "'parte' (el extremo sin rombo). Su multiplicidad va en "
                                "multiplicidadDestino."
                            ),
                        },
                        "tipo": {"type": "string", "enum": list(TIPOS_RELACION)},
                        "multiplicidadOrigen": {
                            "type": ["string", "null"],
                            "description": "La multiplicidad escrita junto a claseOrigen (no la de claseDestino). null si no hay ninguna escrita.",
                        },
                        "multiplicidadDestino": {
                            "type": ["string", "null"],
                            "description": "La multiplicidad escrita junto a claseDestino (no la de claseOrigen). null si no hay ninguna escrita.",
                        },
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
            },
        },
        "required": ["confianza", "advertencia", "clases", "relaciones"],
        "additionalProperties": False,
    },
}

_PROMPT_SISTEMA = (
    "Analizás una fotografía o captura de un diagrama de clases UML (dibujado a mano, en una "
    "pizarra, o generado por una herramienta de diagramación) y devolvés su estructura en el "
    "schema JSON dado.\n\n"
    "Para cada clase: su nombre. Para cada atributo: visibilidad ('publico' si no se distingue el "
    "símbolo +/-/# en la imagen), 'tipo' con el tipo de dato tal como aparece (ej. 'String', 'int', "
    "'Date'; null si no hay ninguno visible) y 'texto' con SOLO el nombre del atributo, sin el tipo "
    "de dato mezclado (ej. si la imagen dice 'String nombre', tipo='String' y texto='nombre'). Para "
    "cada método: visibilidad y 'texto' con la declaración COMPLETA tal como aparece en la imagen, "
    "incluyendo parámetros y tipo de retorno si están indicados.\n\n"
    "Para cada relación, identificá el tipo UML por su símbolo gráfico exacto, no lo asumas por "
    "default:\n"
    "- herencia/generalización: la línea termina en un TRIÁNGULO HUECO (sin relleno) apuntando a "
    "la clase padre. Las relaciones de herencia NUNCA llevan multiplicidad: multiplicidadOrigen y "
    "multiplicidadDestino deben ir en null.\n"
    "- composición: la línea termina en un ROMBO RELLENO (sólido) del lado del 'todo'.\n"
    "- agregación: la línea termina en un ROMBO HUECO (sin relleno) del lado del 'todo'.\n"
    "- dependencia: línea PUNTEADA con una flecha abierta simple.\n"
    "- asociación: línea simple sin símbolos especiales en los extremos; puede o no tener "
    "multiplicidades (números o rangos como '1', '0..*', '1..*') escritas cerca de cada extremo — "
    "si no hay ninguna escrita, usá null, no inventes un valor.\n\n"
    "IMPORTANTE — composición vs. agregación vs. asociación: estas tres se distinguen ÚNICAMENTE "
    "por la presencia y relleno del rombo. Si no ves un rombo con claridad en ninguno de los dos "
    "extremos de la línea, es asociación. No reportes composición ni agregación 'por si acaso' o "
    "porque las clases parezcan tener una relación de pertenencia lógica (ej. un 'Libro' y un "
    "'Autor'); guiate solo por el símbolo gráfico presente en la imagen. Si hay un rombo visible "
    "pero no podés distinguir con confianza si está relleno o hueco, elegí agregación y bajá "
    "'confianza' a 'media'.\n\n"
    "IMPORTANTE — a qué clase y multiplicidad corresponde cada campo: claseOrigen/claseDestino "
    "siguen esta convención según el tipo:\n"
    "- herencia: claseOrigen es la subclase (de donde sale la línea), claseDestino la superclase "
    "(donde está el triángulo).\n"
    "- composición/agregación: claseOrigen es el 'todo' (el lado del rombo), claseDestino es la "
    "'parte' (el otro extremo, sin rombo).\n"
    "- asociación/dependencia: no hay un orden obligatorio entre las dos clases.\n"
    "En todos los casos, una vez elegida cuál es claseOrigen y cuál claseDestino, la multiplicidad "
    "que va en multiplicidadOrigen es la que está escrita junto a claseOrigen en la imagen, y la "
    "que va en multiplicidadDestino es la escrita junto a claseDestino — NUNCA cruces una "
    "multiplicidad con la clase del otro extremo. Ejemplo: si 'Persona' tiene '1' escrito junto a "
    "ella y 'Pedido' tiene '0..*' escrito junto a él, y elegís claseOrigen='Persona' / "
    "claseDestino='Pedido', entonces multiplicidadOrigen='1' y multiplicidadDestino='0..*'.\n\n"
    "Revisá con cuidado que quede reportada CADA línea de relación visible en la imagen entre dos "
    "clases, incluso si se cruza visualmente con otras líneas del diagrama.\n\n"
    "Si la imagen es de baja calidad, está incompleta, o no estás seguro de haber reconocido todo "
    "correctamente, igual devolvé lo que sí pudiste reconocer, pero usá confianza='baja' o 'media' "
    "y explicá el motivo en 'advertencia'. Si no se reconoce ninguna clase en la imagen, devolvé "
    "'clases' y 'relaciones' vacíos."
)


def interpretar_imagen(imagen_bytes: bytes, content_type: str) -> dict:
    """Devuelve un dict que cumple DIAGRAMA_JSON_SCHEMA.

    Lanza ServicioIANoDisponibleError si falla la llamada a OpenAI.
    """
    cliente = cliente_openai()
    imagen_b64 = base64.b64encode(imagen_bytes).decode("ascii")
    try:
        respuesta = cliente.chat.completions.create(
            model=MODELO_VISION,
            messages=[
                {"role": "system", "content": _PROMPT_SISTEMA},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Reconstruí el diagrama de clases de esta imagen."},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{content_type};base64,{imagen_b64}"},
                        },
                    ],
                },
            ],
            response_format={"type": "json_schema", "json_schema": DIAGRAMA_JSON_SCHEMA},
        )
        return json.loads(respuesta.choices[0].message.content)
    except ServicioIANoDisponibleError:
        raise
    except Exception as exc:
        raise ServicioIANoDisponibleError(
            "No se pudo analizar la imagen (servicio de visión no disponible)."
        ) from exc


def _generar_id(prefijo: str) -> str:
    return f"{prefijo}-{uuid.uuid4().hex[:10]}"


def _items(lista: list[dict] | None, prefijo: str) -> list[dict]:
    return [
        {
            "id": _generar_id(prefijo),
            "visibilidad": item["visibilidad"],
            "tipo": item.get("tipo") or "",
            "texto": item["texto"],
        }
        for item in (lista or [])
    ]


def _buscar_nodo_por_nombre(nodes: list[dict], nombre: str | None) -> dict | None:
    nombre_normalizado = normalizar(nombre)
    if not nombre_normalizado:
        return None
    return next(
        (n for n in nodes if normalizar(n.get("data", {}).get("nombre")) == nombre_normalizado),
        None,
    )


def _siguiente_posicion(indice: int, offset_x: int) -> dict:
    columna = indice % 3
    fila = indice // 3
    return {"x": offset_x + columna * 260, "y": 80 + fila * 220}


def construir_contenido(contenido_actual: dict, resultado: dict) -> tuple[dict, list[str]]:
    """Función pura: agrega a una copia de `contenido_actual` las clases y
    relaciones reconocidas en `resultado`, sin tocar nada de lo existente.
    Las relaciones que referencian una clase no reconocible (ni entre las
    nuevas ni entre las existentes) se omiten en vez de abortar todo el
    import — es una reconstrucción best-effort.

    Devuelve `(nuevo_contenido, relaciones_omitidas)`, donde `relaciones_omitidas`
    describe (ej. "Socio → Prestamo") las relaciones que el modelo reportó pero
    no se pudieron aplicar, para que el llamador pueda avisarle al usuario en
    vez de que desaparezcan en silencio.
    """
    nodes = [dict(n) for n in contenido_actual.get("nodes", [])]
    edges = list(contenido_actual.get("edges", []))

    offset_x = max((n.get("position", {}).get("x", 0) for n in nodes), default=-260) + 260

    nodos_nuevos = []
    for indice, clase in enumerate(resultado.get("clases", [])):
        nodo = {
            "id": _generar_id("clase"),
            "type": "clase",
            "position": _siguiente_posicion(indice, offset_x),
            "data": {
                "nombre": clase.get("nombre") or "ClaseSinNombre",
                "atributos": _items(clase.get("atributos"), "atributos"),
                "metodos": _items(clase.get("metodos"), "metodos"),
            },
        }
        nodos_nuevos.append(nodo)

    nodes.extend(nodos_nuevos)

    relaciones_omitidas = []
    for rel in resultado.get("relaciones", []):
        origen = _buscar_nodo_por_nombre(nodes, rel.get("claseOrigen"))
        destino = _buscar_nodo_por_nombre(nodes, rel.get("claseDestino"))
        if origen is None or destino is None:
            relaciones_omitidas.append(f'{rel.get("claseOrigen")} → {rel.get("claseDestino")}')
            continue
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

    return {"nodes": nodes, "edges": edges}, relaciones_omitidas
