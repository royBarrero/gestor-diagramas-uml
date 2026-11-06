"""Router del chat grupal de un proyecto (CU15). Los mensajes se envían por
REST y se difunden por Socket.IO a la sala del proyecto. Si un mensaje menciona
al agente, la respuesta se genera en segundo plano y llega como otro mensaje.
"""

import asyncio

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import SessionLocal, get_db
from app.core.deps import get_current_user
from app.core.permisos import exigir_miembro, obtener_proyecto_o_404
from app.models.diagrama import Diagrama
from app.models.mensaje_proyecto import MensajeProyecto
from app.models.proyecto import Proyecto
from app.models.usuario import Usuario
from app.realtime import emitir_mensaje, room_proyecto, sio
from app.schemas.mensaje_proyecto import MensajeCrear, MensajeOut
from app.services import agente_chat
from app.services.ia_cliente import ServicioIANoDisponibleError

router = APIRouter(prefix="/proyectos/{proyecto_id}/mensajes", tags=["chat"])

MENSAJES_DE_CONTEXTO = 20
AVISO_AGENTE_NO_DISPONIBLE = "El agente de IA no está disponible en este momento."


def _generar_respuesta_agente(proyecto_id: int, mensaje_id: int) -> MensajeOut:
    """Corre en un hilo aparte: tanto la base de datos como el cliente de OpenAI
    son síncronos y bloquearían el tiempo real. La sesión no queda abierta
    mientras se espera a la IA.
    """
    with SessionLocal() as db:
        consulta = db.get(MensajeProyecto, mensaje_id)
        id_autor, autor, texto = consulta.id_usuario, consulta.autor.nombre, consulta.texto
        proyecto = db.get(Proyecto, proyecto_id)
        proyecto_nombre, proyecto_descripcion = proyecto.nombre, proyecto.descripcion
        diagrama = db.query(Diagrama).filter(Diagrama.id_proyecto == proyecto_id).first()
        contenido = (diagrama.contenido if diagrama else None) or {}
        anteriores = (
            db.query(MensajeProyecto)
            .options(joinedload(MensajeProyecto.autor))
            .filter(
                MensajeProyecto.id_proyecto == proyecto_id,
                MensajeProyecto.id < mensaje_id,
                MensajeProyecto.tipo != "sistema",
            )
            .order_by(MensajeProyecto.id.desc())
            .limit(MENSAJES_DE_CONTEXTO)
            .all()
        )
        historial = [
            {"tipo": m.tipo, "autor": m.autor.nombre if m.autor else None, "texto": m.texto}
            for m in reversed(anteriores)
        ]

    try:
        respuesta = agente_chat.responder_consulta(
            autor, texto, proyecto_nombre, proyecto_descripcion, contenido, historial
        )
        nuevo = MensajeProyecto(
            id_proyecto=proyecto_id, tipo="agente", texto=respuesta, id_usuario_destino=id_autor
        )
    except ServicioIANoDisponibleError:
        nuevo = MensajeProyecto(id_proyecto=proyecto_id, tipo="sistema", texto=AVISO_AGENTE_NO_DISPONIBLE)

    with SessionLocal() as db:
        db.add(nuevo)
        db.commit()
        db.refresh(nuevo)
        return MensajeOut.desde_modelo(nuevo)


async def _atender_mencion(proyecto_id: int, mensaje_id: int) -> None:
    room = room_proyecto(proyecto_id)
    await sio.emit("chat_agente_escribiendo", {"activo": True}, room=room)
    try:
        respuesta = await asyncio.to_thread(_generar_respuesta_agente, proyecto_id, mensaje_id)
        await emitir_mensaje(respuesta)
    finally:
        await sio.emit("chat_agente_escribiendo", {"activo": False}, room=room)


@router.get("", response_model=list[MensajeOut])
def listar_mensajes(
    proyecto_id: int,
    antes_de: int | None = None,
    despues_de: int | None = None,
    limite: int = Query(50, ge=1, le=200),
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Devuelve los mensajes del más viejo al más nuevo: con `despues_de`, los
    siguientes a ese id (para ponerse al día al reconectar); si no, los últimos
    `limite`, opcionalmente anteriores a `antes_de` (para cargar más historial).
    """
    proyecto = obtener_proyecto_o_404(proyecto_id, db)
    exigir_miembro(proyecto, usuario_actual, db)

    consulta = (
        db.query(MensajeProyecto)
        .options(joinedload(MensajeProyecto.autor), joinedload(MensajeProyecto.destino))
        .filter(MensajeProyecto.id_proyecto == proyecto_id)
    )
    if despues_de is not None:
        mensajes = (
            consulta.filter(MensajeProyecto.id > despues_de).order_by(MensajeProyecto.id.asc()).limit(limite).all()
        )
    else:
        if antes_de is not None:
            consulta = consulta.filter(MensajeProyecto.id < antes_de)
        mensajes = consulta.order_by(MensajeProyecto.id.desc()).limit(limite).all()
        mensajes.reverse()

    return [MensajeOut.desde_modelo(m) for m in mensajes]


@router.post("", response_model=MensajeOut, status_code=status.HTTP_201_CREATED)
async def enviar_mensaje(
    proyecto_id: int,
    datos: MensajeCrear,
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    proyecto = obtener_proyecto_o_404(proyecto_id, db)
    exigir_miembro(proyecto, usuario_actual, db)

    mensaje = MensajeProyecto(id_proyecto=proyecto_id, id_usuario=usuario_actual.id, tipo="usuario", texto=datos.texto)
    db.add(mensaje)
    db.commit()
    db.refresh(mensaje)

    salida = MensajeOut.desde_modelo(mensaje)
    await emitir_mensaje(salida)

    if agente_chat.menciona_agente(salida.texto):
        sio.start_background_task(_atender_mencion, proyecto_id, salida.id)

    return salida
