"""Integración con OpenAI para CU13: agente asistente conversacional que
orienta al usuario sobre CÓMO usar el sistema (no sobre el contenido de un
diagrama puntual). Aislado acá con el mismo criterio que
`comando_voz.py`/`digitalizacion_imagen.py`, para que el resto del backend no
dependa del SDK/API key de OpenAI.
"""

from app.services.ia_cliente import ServicioIANoDisponibleError, cliente_openai

MODELO_ASISTENTE = "gpt-4o-mini"

_PROMPT_SISTEMA = (
    "Sos el asistente de ayuda integrado de un sistema web de diagramación de "
    "clases UML colaborativo. Tu trabajo es orientar al usuario sobre CÓMO usar "
    "las funcionalidades del sistema, no resolver el contenido de su diagrama "
    "puntual. Funcionalidades disponibles:\n"
    "- Proyectos: crear/editar/eliminar proyectos, invitar colaboradores por "
    "email (solo el administrador del proyecto puede gestionar miembros).\n"
    "- Editor de diagramas (Pizarra): crear clases con atributos y métodos, y "
    "relaciones entre clases (asociación, agregación, composición, herencia, "
    "dependencia), con multiplicidades en los extremos.\n"
    "- Colaboración en tiempo real: varios usuarios pueden editar el mismo "
    "diagrama a la vez, los cambios se sincronizan solos.\n"
    "- Exportar/importar el diagrama en JSON, imagen (PNG) o XMI (compatible "
    "con Enterprise Architect).\n"
    "- Comando de voz: grabar un comando hablado para crear/editar clases o "
    "relaciones sin usar el mouse.\n"
    "- Digitalizar diagrama por foto: subir una fotografía de un diagrama "
    "dibujado a mano o en una pizarra y que el sistema lo reconstruya.\n"
    "- Generar backend: a partir del diagrama, generar un proyecto Spring "
    "Boot completo (entidades JPA, DTOs, repositorios, servicios, "
    "controladores REST) listo para descargar y correr.\n"
    "- Generar frontend: a partir del backend ya generado, generar una app "
    "Flutter con pantallas de listado y formulario para cada clase.\n\n"
    "Respondé siempre en español, de forma breve, concreta y orientada a la "
    "acción — si hace falta, guiá paso a paso (ej. 'hacé clic en...', "
    "'andá a...'). Si la pregunta no tiene que ver con el uso del sistema, o "
    "no la entendés, pedile amablemente al usuario que la reformule o "
    "aclare a qué funcionalidad se refiere, en vez de inventar una respuesta."
)


def responder_pregunta(pregunta: str, contexto_pantalla: str | None, historial: list[dict]) -> str:
    """Devuelve el texto de la respuesta del asistente.

    `historial` es la conversación previa de este chat, como lista de dicts
    `{"rol": "usuario" | "asistente", "texto": str}` — el frontend no
    persiste nada, la reenvía en cada pregunta para darle memoria a la
    conversación dentro de la sesión.

    Lanza ServicioIANoDisponibleError si falla la llamada a OpenAI.
    """
    cliente = cliente_openai()

    mensajes = [{"role": "system", "content": _PROMPT_SISTEMA}]
    if contexto_pantalla:
        mensajes.append({"role": "system", "content": f"Pantalla actual del usuario: {contexto_pantalla}"})
    for turno in historial:
        rol = "assistant" if turno.get("rol") == "asistente" else "user"
        mensajes.append({"role": rol, "content": turno.get("texto", "")})
    mensajes.append({"role": "user", "content": pregunta})

    try:
        respuesta = cliente.chat.completions.create(model=MODELO_ASISTENTE, messages=mensajes)
        return respuesta.choices[0].message.content
    except ServicioIANoDisponibleError:
        raise
    except Exception as exc:
        raise ServicioIANoDisponibleError("El asistente no está disponible en este momento.") from exc
