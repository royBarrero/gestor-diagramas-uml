"""Integración con OpenAI para CU09: reconocimiento de un diagrama de clases
a partir de una fotografía (visión por computadora) y reconstrucción de esa
estructura como nodos/edges para agregar al diagrama actual.
"""

import base64
import io
import json
import re
import uuid

from PIL import Image, ImageOps

from app.services.constantes_diagrama import TIPOS_RELACION, VISIBILIDADES, normalizar
from app.services.ia_cliente import ServicioIANoDisponibleError, cliente_openai

# Modelo más fuerte que el resto de los servicios de IA: gpt-4o-mini leía mal
# la escritura a mano de pizarras (multiplicidades cruzadas, relaciones perdidas).
MODELO_VISION = "gpt-4.1"

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
                        "lecturaVisual": {
                            "type": "string",
                            "description": (
                                "Antes de llenar el resto de los campos: describí con tus palabras "
                                "esta línea — qué dos clases toca, qué símbolo tiene en cada punta "
                                "(nada, rombo, triángulo, flecha), qué está escrito junto a CADA "
                                "punta (qué texto está pegado al extremo que toca a cada clase) y "
                                "si de su medio sale una línea punteada hacia otra clase."
                            ),
                        },
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
                        "claseAsociacion": {
                            "type": ["string", "null"],
                            "description": (
                                "Nombre de la clase de asociación de esta relación: la clase a la "
                                "que llega una línea PUNTEADA SIN FLECHA que sale del medio de esta "
                                "línea. null si no hay ninguna."
                            ),
                        },
                    },
                    "required": [
                        "lecturaVisual",
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
    "de dato mezclado (ej. si la imagen dice 'String nombre', tipo='String' y texto='nombre'), "
    "escrito en camelCase con minúscula inicial según la convención UML aunque a mano esté en "
    "mayúscula (ej. 'Precio Unit' -> 'precioUnit', 'Id' -> 'id'). Para "
    "cada método: visibilidad y 'texto' con la declaración COMPLETA tal como aparece en la imagen, "
    "incluyendo parámetros y tipo de retorno si están indicados.\n\n"
    "Para cada relación, identificá el tipo UML por su símbolo gráfico exacto, no lo asumas por "
    "default:\n"
    "- herencia/generalización: la línea termina en un TRIÁNGULO HUECO (sin relleno) apuntando a "
    "la clase padre. Las relaciones de herencia NUNCA llevan multiplicidad: multiplicidadOrigen y "
    "multiplicidadDestino deben ir en null.\n"
    "- composición: la línea termina en un ROMBO RELLENO (sólido) del lado del 'todo'.\n"
    "- agregación: la línea termina en un ROMBO HUECO (sin relleno) del lado del 'todo'.\n"
    "- dependencia: línea PUNTEADA con una flecha abierta simple, que va DE UNA CLASE A OTRA "
    "CLASE.\n"
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
    "IMPORTANTE — cómo decidir a qué clase pertenece una multiplicidad escrita a mano: cada "
    "multiplicidad pertenece al EXTREMO DE LÍNEA junto al que está escrita, es decir, a la clase "
    "que toca ESA punta de la línea. No la asignes a la caja de clase que te parezca más cercana "
    "en el dibujo, ni asumas un '1' por default: en las pizarras es común que el texto quede un "
    "poco separado de la caja. Ejemplo: una línea une 'Venta' (arriba) con 'Cliente' (abajo); "
    "junto a la punta que toca a Venta hay un '*' y junto a la punta que toca a Cliente hay un "
    "'1' → la multiplicidad de Venta es '*' y la de Cliente es '1' (cada Venta tiene un Cliente, "
    "un Cliente tiene muchas Ventas). Leé cada número o símbolo tal cual está escrito ('*', '1', "
    "'0..1', '1..*', '0..*'); no conviertas '*' en '0..*' ni al revés. A mano, el '*' suele "
    "dibujarse como una estrellita, un '✱', una 'x' o un '*' seguido de un punto, a veces muy "
    "chico y pegado al borde de la caja de la clase: revisá los recortes ampliados en cada punta "
    "antes de decidir, y no lo confundas con un '1'. Usá el campo "
    "'lecturaVisual' para describir primero qué ves en cada punta y recién después llená los "
    "campos de multiplicidad de forma coherente con esa descripción.\n\n"
    "CLASE DE ASOCIACIÓN: si de la MITAD de una línea de asociación sale una línea PUNTEADA SIN "
    "FLECHA que termina en otra clase (típico en relaciones muchos-a-muchos, ej. 'Detalle' "
    "colgando de la línea entre 'Venta' y 'Producto'), esa clase es la clase de asociación de "
    "esa relación: reportá la asociación normalmente entre las dos clases de los extremos (con "
    "sus multiplicidades) y poné el nombre de la clase colgada en 'claseAsociacion'. La clase "
    "de asociación se reporta igual en 'clases' con sus atributos, pero la línea punteada NO es "
    "una relación aparte: no la reportes como dependencia, ni como agregación/composición, ni "
    "inventes relaciones entre la clase de asociación y las clases de los extremos. En el resto "
    "de las relaciones, 'claseAsociacion' va en null.\n\n"
    "Revisá con cuidado que quede reportada CADA línea continua visible en la imagen entre dos "
    "clases (cada una es una relación), incluso si se cruza visualmente con otras líneas del "
    "diagrama o si tiene una línea punteada colgando de su medio.\n\n"
    "Si la imagen es de baja calidad, está incompleta, o no estás seguro de haber reconocido todo "
    "correctamente, igual devolvé lo que sí pudiste reconocer, pero usá confianza='baja' o 'media' "
    "y explicá el motivo en 'advertencia'. Si no se reconoce ninguna clase en la imagen, devolvé "
    "'clases' y 'relaciones' vacíos."
)


# Solapamiento entre recortes, para que una multiplicidad o una línea que cae
# justo en el borde de un cuadrante aparezca completa en al menos uno.
SOLAPAMIENTO_RECORTES = 0.2

_NOMBRES_RECORTES = ("superior izquierdo", "superior derecho", "inferior izquierdo", "inferior derecho")


def _data_uri(imagen: Image.Image) -> str:
    buffer = io.BytesIO()
    imagen.save(buffer, format="JPEG", quality=92)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def _recortes(imagen_bytes: bytes) -> list[str]:
    """Divide la imagen en 4 cuadrantes solapados y devuelve cada uno como
    data-URI. La API reduce la foto completa a ~1024x768 incluso con
    detail='high', y en pizarras a mano eso borra trazos chicos (un '*' pegado
    al borde de una clase); cada cuadrante llega a resolución casi nativa.
    Si Pillow no puede abrir la imagen, devuelve [] y se usa solo la completa.
    """
    try:
        imagen = ImageOps.exif_transpose(Image.open(io.BytesIO(imagen_bytes))).convert("RGB")
    except Exception:
        return []
    ancho, alto = imagen.size
    medio_ancho = int(ancho * (0.5 + SOLAPAMIENTO_RECORTES / 2))
    medio_alto = int(alto * (0.5 + SOLAPAMIENTO_RECORTES / 2))
    cajas = [
        (0, 0, medio_ancho, medio_alto),
        (ancho - medio_ancho, 0, ancho, medio_alto),
        (0, alto - medio_alto, medio_ancho, alto),
        (ancho - medio_ancho, alto - medio_alto, ancho, alto),
    ]
    return [_data_uri(imagen.crop(caja)) for caja in cajas]


def _bloque_imagen(url: str) -> dict:
    return {"type": "image_url", "image_url": {"url": url, "detail": "high"}}


def interpretar_imagen(imagen_bytes: bytes, content_type: str) -> dict:
    """Devuelve un dict que cumple DIAGRAMA_JSON_SCHEMA.

    Lanza ServicioIANoDisponibleError si falla la llamada a OpenAI.
    """
    cliente = cliente_openai()
    imagen_b64 = base64.b64encode(imagen_bytes).decode("ascii")
    contenido = [
        {"type": "text", "text": "Reconstruí el diagrama de clases de esta imagen (imagen completa):"},
        _bloque_imagen(f"data:{content_type};base64,{imagen_b64}"),
    ]
    recortes = _recortes(imagen_bytes)
    if recortes:
        contenido.append(
            {
                "type": "text",
                "text": (
                    "A continuación, 4 recortes AMPLIADOS de la MISMA imagen (cuadrantes "
                    "solapados), para que leas los detalles chicos: multiplicidades, "
                    "asteriscos, símbolos en las puntas de las líneas y nombres de "
                    "atributos. No son clases ni relaciones distintas: usalos solo para "
                    "leer mejor lo que aparece en la imagen completa, sin duplicar nada."
                ),
            }
        )
        for nombre, url in zip(_NOMBRES_RECORTES, recortes):
            contenido.append({"type": "text", "text": f"Recorte {nombre}:"})
            contenido.append(_bloque_imagen(url))
    try:
        respuesta = cliente.chat.completions.create(
            model=MODELO_VISION,
            temperature=0,
            messages=[
                {"role": "system", "content": _PROMPT_SISTEMA},
                {"role": "user", "content": contenido},
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


def _normalizar_multiplicidad(valor: str | None) -> str | None:
    """Pasa la notación informal 'n' (ej. '1..n', 'n') al '*' de UML 2.5 y
    quita espacios ('1 .. *' -> '1..*')."""
    if not valor:
        return None
    return re.sub(r"\b[nN]\b", "*", valor.replace(" ", ""))


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
        data = {
            "tipo": rel.get("tipo"),
            "multiplicidadOrigen": _normalizar_multiplicidad(rel.get("multiplicidadOrigen")),
            "multiplicidadDestino": _normalizar_multiplicidad(rel.get("multiplicidadDestino")),
            "nombre": rel.get("nombre"),
            "estiloLinea": "recta",
        }
        # La clase de asociación no es un edge aparte: se guarda como referencia
        # al nodo dentro de la propia relación y RelacionEdge dibuja la punteada.
        if rel.get("claseAsociacion"):
            nodo_asociacion = _buscar_nodo_por_nombre(nodes, rel.get("claseAsociacion"))
            if nodo_asociacion is None:
                relaciones_omitidas.append(
                    f'clase de asociación {rel.get("claseAsociacion")} de '
                    f'{rel.get("claseOrigen")} → {rel.get("claseDestino")}'
                )
            else:
                data["claseAsociacion"] = nodo_asociacion["id"]
        edges.append(
            {
                "id": _generar_id("rel"),
                "source": origen["id"],
                "target": destino["id"],
                "type": "relacion",
                "data": data,
            }
        )

    return {"nodes": nodes, "edges": edges}, relaciones_omitidas
