from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, invitaciones, proyectos

app = FastAPI(title="Gestor de Diagramas UML - API")

# Habilitar CORS para que el frontend (React en localhost:5173) pueda comunicarse con el backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(proyectos.router)
app.include_router(invitaciones.router)

@app.get("/")
def read_root():
    return {"mensaje": "API del Gestor de Diagramas UML funcionando correctamente"}