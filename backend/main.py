import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_cors_origins
from app.realtime import sio
from app.routers import asistente, auth, diagramas, generacion, invitaciones, proyectos

api = FastAPI(title="Gestor de Diagramas UML - API")

# Habilitar CORS para que el frontend pueda comunicarse con el backend.
# Orígenes configurables vía CORS_ORIGINS (ver backend/.env.example).
api.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

api.include_router(auth.router)
api.include_router(proyectos.router)
api.include_router(invitaciones.router)
api.include_router(diagramas.router)
api.include_router(generacion.router)
api.include_router(asistente.router)

@api.get("/")
def read_root():
    return {"mensaje": "API del Gestor de Diagramas UML funcionando correctamente"}

# Se envuelve la app de FastAPI con el servidor de Socket.IO (CU07) sin
# cambiar el nombre `app` que usa `uvicorn main:app --reload`.
app = socketio.ASGIApp(sio, other_asgi_app=api)
