"""Servidor de WebSockets (Socket.IO) para CU07: colaboración en tiempo
real sobre un diagrama. Roster de conectados en memoria de proceso — alcanza
para el único worker de uvicorn con el que corre hoy el backend.
"""

from urllib.parse import parse_qs

import socketio
from socketio.exceptions import ConnectionRefusedError

from app.core.database import SessionLocal
from app.core.deps import obtener_usuario_desde_token
from app.core.permisos import obtener_proyecto_o_404, rol_de_usuario_en_proyecto
from app.models.diagrama import Diagrama

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=["http://localhost:5173"])

# room -> {sid: {"id": usuario_id, "nombre": nombre}}
salas: dict[str, dict[str, dict]] = {}


def _room(diagrama_id: str) -> str:
    return f"diagrama_{diagrama_id}"


def room_usuario(usuario_id: int) -> str:
    return f"usuario_{usuario_id}"


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
        if diagrama_id is not None:
            diagrama = db.query(Diagrama).filter(Diagrama.id == diagrama_id).first()
            if diagrama is None:
                raise ConnectionRefusedError("El diagrama no existe.")

            proyecto = obtener_proyecto_o_404(diagrama.id_proyecto, db)
            if rol_de_usuario_en_proyecto(proyecto, usuario, db) is None:
                raise ConnectionRefusedError("No tenés acceso a este proyecto.")
            room = _room(diagrama_id)
    finally:
        db.close()

    await sio.save_session(sid, {"room": room, "usuario_id": usuario.id, "nombre": usuario.nombre})
    await sio.enter_room(sid, room_usuario(usuario.id))

    if room:
        await sio.enter_room(sid, room)
        salas.setdefault(room, {})[sid] = {"id": usuario.id, "nombre": usuario.nombre, "claseId": None}
        await _emitir_colaboradores(room)


@sio.event
async def disconnect(sid):
    sesion = await sio.get_session(sid)
    room = sesion.get("room") if sesion else None
    if room:
        salas.get(room, {}).pop(sid, None)
        await _emitir_colaboradores(room)


@sio.event
async def cambio_diagrama(sid, data):
    sesion = await sio.get_session(sid)
    if sesion:
        await sio.emit("cambio_diagrama", data, room=sesion["room"], skip_sid=sid)


@sio.event
async def seleccion(sid, data):
    sesion = await sio.get_session(sid)
    if not sesion:
        return
    room = sesion["room"]
    if sid in salas.get(room, {}):
        salas[room][sid]["claseId"] = (data or {}).get("claseId")
        await _emitir_colaboradores(room)
