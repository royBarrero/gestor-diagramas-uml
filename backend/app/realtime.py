"""Servidor de WebSockets (Socket.IO) para CU07: colaboración en tiempo
real sobre un diagrama. Roster de conectados en memoria de proceso — alcanza
para el único worker de uvicorn con el que corre hoy el backend.
"""

import asyncio
import logging
from urllib.parse import parse_qs

import socketio
from socketio.exceptions import ConnectionRefusedError

from app.core.config import origen_permitido
from app.core.database import SessionLocal
from app.core.deps import obtener_usuario_desde_token
from app.core.permisos import obtener_proyecto_o_404, rol_de_usuario_en_proyecto
from app.models.diagrama import Diagrama
from app.schemas.mensaje_proyecto import MensajeOut
from app.schemas.historial_cambio import HistorialOut
from app.services.documento_vivo import DocumentosVivos
from app.services.historial_cambios import HistorialCambios
from app.services.revisor_diagrama import RevisorDiagrama

logger = logging.getLogger(__name__)

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=origen_permitido)

# room -> {sid: {"id": usuario_id, "nombre": nombre}}
salas: dict[str, dict[str, dict]] = {}


def _room(diagrama_id: str) -> str:
    return f"diagrama_{diagrama_id}"


def room_usuario(usuario_id: int) -> str:
    return f"usuario_{usuario_id}"


def room_proyecto(proyecto_id: int) -> str:
    return f"proyecto_{proyecto_id}"


async def emitir_mensaje(mensaje: MensajeOut) -> None:
    """Difunde un mensaje del chat grupal a la sala de su proyecto."""
    await sio.emit("chat_mensaje", mensaje.model_dump(mode="json"), room=room_proyecto(mensaje.id_proyecto))


async def emitir_mensaje_actualizado(mensaje: MensajeOut) -> None:
    """Un mensaje ya publicado cambió: el estado de sus botones, o se resolvió la sugerencia."""
    await sio.emit(
        "chat_mensaje_actualizado", mensaje.model_dump(mode="json"), room=room_proyecto(mensaje.id_proyecto)
    )


async def emitir_historial(entrada: HistorialOut) -> None:
    """CU18: una entrada nueva del historial, para que la lista se actualice en vivo."""
    await sio.emit("historial_cambio", entrada.model_dump(mode="json"), room=room_proyecto(entrada.id_proyecto))


# CU16: sugerencias automáticas del agente sobre las clases que se editan.
revisor = RevisorDiagrama(publicar=emitir_mensaje)
# CU17: la versión viva de cada diagrama, que no depende del autoguardado de nadie.
documentos = DocumentosVivos()
# CU18: quién cambió qué y cuándo.
historial = HistorialCambios(publicar=emitir_historial)


async def emitir_contenido(diagrama_id: int, contenido: dict, cambios: dict) -> None:
    """Un cambio hecho en el servidor. Lleva `cambios` como los de cualquier cliente,
    para que se fusione sin pisar lo que los demás están editando."""
    await sio.emit("cambio_diagrama", {**contenido, "cambios": cambios}, room=_room(diagrama_id))


async def publicar_contenido(
    proyecto_id: int, diagrama_id: int, usuario_id: int, contenido: dict, origen: str, antes: dict
) -> None:
    """Un cambio de un endpoint a pedido de un usuario (voz, foto, importación). `antes` lo
    pasa quien llama porque, sin nadie conectado, no hay documento vivo."""
    cambios = documentos.reemplazar(proyecto_id, contenido)
    historial.registrar_operacion(proyecto_id, usuario_id, origen, antes, contenido)
    await emitir_contenido(diagrama_id, contenido, cambios)
    revisor.registrar_cambio(proyecto_id, usuario_id, contenido)


def nombre_en_sala(diagrama_id: int, usuario_id: int) -> str | None:
    for info in salas.get(_room(diagrama_id), {}).values():
        if info["id"] == usuario_id:
            return info["nombre"]
    return None


def _guardar_documento(diagrama_id: int, contenido: dict) -> None:
    db = SessionLocal()
    try:
        diagrama = db.query(Diagrama).filter(Diagrama.id == diagrama_id).first()
        if diagrama is not None:
            diagrama.contenido = contenido
            db.commit()
    finally:
        db.close()


async def sacar_de_proyecto(usuario_id: int, proyecto_id: int) -> None:
    """Al quitar un miembro, cierra sus sockets abiertos en ese proyecto: deja de
    recibir el chat y de recibir o enviar cambios del diagrama. Su socket de
    notificaciones y los de otros proyectos siguen conectados."""
    revisor.cancelar_usuario(proyecto_id, usuario_id)
    for sid, _ in list(sio.manager.get_participants("/", room_usuario(usuario_id))):
        sesion = await sio.get_session(sid)
        if sesion and sesion.get("proyecto_id") == proyecto_id:
            await sio.disconnect(sid)


async def _emitir_colaboradores(room: str) -> None:
    vistos: set[int] = set()
    colaboradores = []
    for info in salas.get(room, {}).values():
        if info["id"] not in vistos:
            vistos.add(info["id"])
            colaboradores.append(info)
    await sio.emit("colaboradores", colaboradores, room=room)


@sio.event
async def connect(sid, environ, auth):
    token = (auth or {}).get("token")
    if not token:
        raise ConnectionRefusedError("Falta token.")

    query = parse_qs(environ.get("QUERY_STRING", ""))
    diagrama_id = (query.get("diagramaId") or [None])[0]
    # CU19: la app móvil solo mira. Recibe los cambios, el chat y el historial, pero no
    # figura como conectada en la pizarra ni puede enviar cambios.
    solo_lectura = (query.get("modo") or [None])[0] == "lectura"
    if diagrama_id is not None:
        try:
            diagrama_id = int(diagrama_id)
        except ValueError:
            raise ConnectionRefusedError("diagramaId inválido.")

    db = SessionLocal()
    try:
        usuario = obtener_usuario_desde_token(token, db)
        if usuario is None:
            raise ConnectionRefusedError("Token inválido.")

        room = None
        proyecto_id = None
        if diagrama_id is not None:
            diagrama = db.query(Diagrama).filter(Diagrama.id == diagrama_id).first()
            if diagrama is None:
                raise ConnectionRefusedError("El diagrama no existe.")

            proyecto = obtener_proyecto_o_404(diagrama.id_proyecto, db)
            if rol_de_usuario_en_proyecto(proyecto, usuario, db) is None:
                raise ConnectionRefusedError("No tenés acceso a este proyecto.")
            room = _room(diagrama_id)
            proyecto_id = proyecto.id
            contenido = diagrama.contenido
    finally:
        db.close()

    await sio.save_session(
        sid,
        {
            "room": room,
            "diagrama_id": diagrama_id,
            "proyecto_id": proyecto_id,
            "usuario_id": usuario.id,
            "nombre": usuario.nombre,
            "solo_lectura": solo_lectura,
        },
    )
    await sio.enter_room(sid, room_usuario(usuario.id))

    if room:
        await sio.enter_room(sid, room)
        await sio.enter_room(sid, room_proyecto(proyecto_id))
        if solo_lectura:
            return
        salas.setdefault(room, {})[sid] = {"id": usuario.id, "nombre": usuario.nombre, "claseId": None}
        revisor.abrir_proyecto(proyecto_id, documentos.abrir(proyecto_id, contenido))
        await _emitir_colaboradores(room)


@sio.event
async def disconnect(sid):
    sesion = await sio.get_session(sid)
    room = sesion.get("room") if sesion else None
    if room and not sesion.get("solo_lectura"):
        sala = salas.get(room, {})
        sala.pop(sid, None)
        # Con otra pestaña abierta el usuario sigue en la pizarra.
        if not any(info["id"] == sesion["usuario_id"] for info in sala.values()):
            revisor.usuario_desconectado(sesion["proyecto_id"], sesion["usuario_id"])
            historial.usuario_desconectado(sesion["proyecto_id"], sesion["usuario_id"])
        if not sala:
            salas.pop(room, None)
            revisor.cerrar_proyecto(sesion["proyecto_id"])
            historial.cerrar_proyecto(sesion["proyecto_id"])
            await _cerrar_documento(room, sesion["proyecto_id"], sesion["diagrama_id"])
        await _emitir_colaboradores(room)


async def _cerrar_documento(room: str, proyecto_id: int, diagrama_id: int) -> None:
    """Se fue el último: se guarda lo último, por si se fue antes del autoguardado. Si
    alguien entró mientras tanto, el documento sigue abierto."""
    contenido = documentos.obtener(proyecto_id)
    try:
        if contenido is not None:
            await asyncio.to_thread(_guardar_documento, diagrama_id, contenido)
    except Exception:
        logger.exception("No se pudo guardar el diagrama %s al cerrarlo", diagrama_id)
    if not salas.get(room):
        documentos.cerrar(proyecto_id)


@sio.event
async def cambio_diagrama(sid, data):
    sesion = await sio.get_session(sid)
    # Sin sala (socket conectado sin diagramaId) no se reenvía: room=None
    # difundiría el cambio a todos los clientes conectados.
    if sesion and sesion["room"] and not sesion.get("solo_lectura"):
        # Sin `await` antes de esto: ningún cambio del agente puede intercalarse.
        antes = documentos.obtener(sesion["proyecto_id"])
        contenido = documentos.aplicar_mensaje(sesion["proyecto_id"], data)
        if contenido is not None:
            propia = salas.get(sesion["room"], {}).get(sid, {}).get("claseId")
            historial.registrar_edicion(sesion["proyecto_id"], sesion["usuario_id"], antes, contenido, propia)
        await sio.emit("cambio_diagrama", data, room=sesion["room"], skip_sid=sid)
        revisor.registrar_cambio(
            sesion["proyecto_id"], sesion["usuario_id"], contenido if contenido is not None else data
        )
        # Confirma el envío: lo que el cliente no vea confirmado lo reenvía al reconectar.
        return True


@sio.event
async def seleccion(sid, data):
    sesion = await sio.get_session(sid)
    if not sesion or sesion.get("solo_lectura"):
        return
    room = sesion["room"]
    if sid in salas.get(room, {}):
        clase_id = data.get("claseId") if isinstance(data, dict) else None
        clase_id = clase_id if isinstance(clase_id, str) else None
        salas[room][sid]["claseId"] = clase_id
        revisor.registrar_seleccion(sesion["proyecto_id"], sesion["usuario_id"], clase_id)
        historial.registrar_seleccion(sesion["proyecto_id"], sesion["usuario_id"], clase_id)
        await _emitir_colaboradores(room)


@sio.event
async def actividad(sid):
    """CU17: tocar teclado o mouse con una clase seleccionada, aunque todavía no haya
    un cambio que enviar (por ejemplo, escribiendo un nombre largo)."""
    sesion = await sio.get_session(sid)
    if sesion and sesion["room"] and not sesion.get("solo_lectura"):
        revisor.registrar_actividad(sesion["proyecto_id"], sesion["usuario_id"])


@sio.event
async def silenciar_ia(sid, data):
    sesion = await sio.get_session(sid)
    if sesion and isinstance(data, dict):
        revisor.silenciar(sesion["usuario_id"], bool(data.get("activo")))
