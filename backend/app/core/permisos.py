"""Chequeos de autorización sobre proyectos, compartidos entre routers REST
y el servidor de WebSockets (CU07)."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.miembro_proyecto import MiembroProyecto
from app.models.proyecto import Proyecto
from app.models.usuario import Usuario


def obtener_proyecto_o_404(proyecto_id: int, db: Session) -> Proyecto:
    proyecto = db.query(Proyecto).filter(Proyecto.id == proyecto_id).first()
    if proyecto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El proyecto no existe.",
        )
    return proyecto


def rol_de_usuario_en_proyecto(proyecto: Proyecto, usuario: Usuario, db: Session) -> str | None:
    """Rol del usuario en el proyecto, o None si no es miembro."""
    membresia = (
        db.query(MiembroProyecto)
        .filter(
            MiembroProyecto.id_proyecto == proyecto.id,
            MiembroProyecto.id_usuario == usuario.id,
        )
        .first()
    )
    if membresia:
        return membresia.rol
    if proyecto.id_usuario_creador == usuario.id:
        return "administrador"
    return None


def exigir_miembro(proyecto: Proyecto, usuario: Usuario, db: Session) -> None:
    if rol_de_usuario_en_proyecto(proyecto, usuario, db) is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenés acceso a este proyecto.",
        )
