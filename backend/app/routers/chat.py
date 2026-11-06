"""Router del chat grupal de un proyecto (CU15). Los mensajes se envían por
REST y se difunden por Socket.IO a la sala del proyecto. Si un mensaje menciona
al agente, se atiende en segundo plano: responde con otro mensaje o, si le piden un
cambio, lo aplica (CU17). También están acá los botones de esos cambios.
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import SessionLocal, get_db
from app.core.deps import get_current_user
from app.core.permisos import exigir_miembro, obtener_proyecto_o_404
from app.models.diagrama import Diagrama
from app.models.mensaje_proyecto import MensajeProyecto
from app.models.proyecto import Proyecto
from app.models.usuario import Usuario
from app.realtime import documentos, emitir_mensaje, room_proyecto, sio
from app.schemas.mensaje_proyecto import MensajeCrear, MensajeOut
from app.services import agente_chat, operaciones_agente
from app.services.ia_cliente import ServicioIANoDisponibleError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/proyectos/{proyecto_id}/mensajes", tags=["chat"])

MENSAJES_DE_CONTEXTO = 20
AVISO_AGENTE_NO_DISPONIBLE = "El agente de IA no está disponible en este momento."


def _cargar_contexto(proyecto_id: int, mensaje_id: int) -> dict:
    """La sesión no queda abierta mientras se espera a la IA."""
    with SessionLocal() as db:
        consulta = db.get(MensajeProyecto, mensaje_id)
        proyecto = db.get(Proyecto, proyecto_id)
        diagrama = db.query(Diagrama).filter(Diagrama.id_proyecto == proyecto_id).first()
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
        return {
            "id_autor": consulta.id_usuario,
            "autor": consulta.autor.nombre,
            "texto": consulta.texto,
            "proyecto_nombre": proyecto.nombre,
            "proyecto_descripcion": proyecto.descripcion,
            "contenido": (diagrama.contenido if diagrama else None) or {},
            "historial": [
                {"tipo": m.tipo, "autor": m.autor.nombre if m.autor else None, "texto": m.texto}
                for m in reversed(anteriores)
            ],
        }


async def _responder_mencion(proyecto_id: int, mensaje_id: int, consulta: str | None, id_sugerencia: int | None) -> None:
    contexto = await asyncio.to_thread(_cargar_contexto, proyecto_id, mensaje_id)
    # La versión viva si hay alguien conectado: la base puede estar atrasada.
    contenido = documentos.obtener(proyecto_id) or contexto["contenido"]
    try:
        resultado = await asyncio.to_thread(
            agente_chat.interpretar_mencion,
            contexto["autor"],
            consulta or contexto["texto"],
            contexto["proyecto_nombre"],
            contexto["proyecto_descripcion"],
            contenido,
            contexto["historial"],
        )
        if resultado["tipo"] == "revision":
            texto = await asyncio.to_thread(
                agente_chat.generar_revision, contexto["proyecto_nombre"], contexto["proyecto_descripcion"], contenido
            )
        elif resultado["tipo"] == "texto":
            texto = resultado["texto"]
    except ServicioIANoDisponibleError:
        await operaciones_agente.publicar_mensaje(proyecto_id, "sistema", AVISO_AGENTE_NO_DISPONIBLE)
        return

    if resultado["tipo"] == "operaciones":
        await operaciones_agente.ejecutar_pedido(proyecto_id, resultado["acciones"], contexto["id_autor"], id_sugerencia)
    else:
        await operaciones_agente.publicar_mensaje(proyecto_id, "agente", texto, destino=contexto["id_autor"])


async def _atender_mencion(
    proyecto_id: int, mensaje_id: int, consulta: str | None = None, id_sugerencia: int | None = None
) -> None:
    room = room_proyecto(proyecto_id)
    await sio.emit("chat_agente_escribiendo", {"activo": True}, room=room)
    try:
        await _responder_mencion(proyecto_id, mensaje_id, consulta, id_sugerencia)
    except Exception:
        logger.exception("Error al atender la mención %s", mensaje_id)
        await operaciones_agente.publicar_mensaje(proyecto_id, "sistema", AVISO_AGENTE_NO_DISPONIBLE)
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
        .options(
            joinedload(MensajeProyecto.autor),
            joinedload(MensajeProyecto.destino),
            joinedload(MensajeProyecto.accion),
            joinedload(MensajeProyecto.correcciones),
        )
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


@router.post("/{mensaje_id}/pedir-correccion", response_model=MensajeOut, status_code=status.HTTP_201_CREATED)
async def pedir_correccion(
    proyecto_id: int,
    mensaje_id: int,
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """CU17: le pide al agente que aplique lo que propuso en una sugerencia de CU16."""
    proyecto = obtener_proyecto_o_404(proyecto_id, db)
    exigir_miembro(proyecto, usuario_actual, db)

    sugerencia = db.get(MensajeProyecto, mensaje_id)
    es_sugerencia = (
        sugerencia is not None
        and sugerencia.id_proyecto == proyecto_id
        and sugerencia.tipo == "agente"
        and sugerencia.elemento_referenciado
        and sugerencia.accion is None
    )
    if not es_sugerencia:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Esa sugerencia no existe.")
    if any(a.estado == "aplicada" for a in sugerencia.correcciones):
        raise HTTPException(status.HTTP_409_CONFLICT, "Esa sugerencia ya se resolvió.")

    diagrama = db.query(Diagrama).filter(Diagrama.id_proyecto == proyecto_id).first()
    contenido = documentos.obtener(proyecto_id) or (diagrama.contenido if diagrama else {}) or {}
    clase = next((n for n in contenido.get("nodes", []) if n.get("id") == sugerencia.elemento_referenciado), None)
    if clase is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "La clase de esa sugerencia ya no existe.")
    nombre_clase = (clase.get("data") or {}).get("nombre")

    mensaje = MensajeProyecto(
        id_proyecto=proyecto_id,
        id_usuario=usuario_actual.id,
        tipo="usuario",
        texto=f"Pedí aplicar la corrección que sugirió el agente sobre {nombre_clase}.",
    )
    db.add(mensaje)
    db.commit()
    db.refresh(mensaje)

    salida = MensajeOut.desde_modelo(mensaje)
    await emitir_mensaje(salida)

    consulta = (
        f"Aplicá en la clase {nombre_clase} la corrección que propusiste en esta sugerencia. Si propone varias "
        f"alternativas, elegí la más directa, y si no dice concretamente qué cambiar, pedí aclaración.\n"
        f"Sugerencia: {sugerencia.texto}"
    )
    sio.start_background_task(_atender_mencion, proyecto_id, salida.id, consulta, mensaje_id)

    return salida


async def _resolver_accion(hacer) -> dict:
    """Pasa los rechazos de un botón a un error HTTP, con el motivo para mostrar junto a él."""
    try:
        await hacer
    except operaciones_agente.AccionNoPermitida as exc:
        raise HTTPException(exc.status, exc.detalle) from exc
    return {"ok": True}


@router.post("/acciones/{accion_id}/confirmar")
async def confirmar_accion(
    proyecto_id: int,
    accion_id: int,
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    exigir_miembro(obtener_proyecto_o_404(proyecto_id, db), usuario_actual, db)
    return await _resolver_accion(operaciones_agente.confirmar(proyecto_id, accion_id, usuario_actual.id))


@router.post("/acciones/{accion_id}/cancelar")
async def cancelar_accion(
    proyecto_id: int,
    accion_id: int,
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    exigir_miembro(obtener_proyecto_o_404(proyecto_id, db), usuario_actual, db)
    return await _resolver_accion(operaciones_agente.cancelar(proyecto_id, accion_id, usuario_actual.id))


@router.post("/acciones/{accion_id}/deshacer")
async def deshacer_accion(
    proyecto_id: int,
    accion_id: int,
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    exigir_miembro(obtener_proyecto_o_404(proyecto_id, db), usuario_actual, db)
    return await _resolver_accion(
        operaciones_agente.deshacer(proyecto_id, accion_id, usuario_actual.id, usuario_actual.nombre)
    )
