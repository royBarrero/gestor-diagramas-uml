"""Router de diagramas. CU06: lectura y guardado del contenido del
diagrama de clases (nodos, atributos, métodos y relaciones).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.diagrama import Diagrama
from app.models.miembro_proyecto import MiembroProyecto
from app.models.proyecto import Proyecto
from app.models.usuario import Usuario
from app.schemas.diagrama import DiagramaActualizar, DiagramaOut

router = APIRouter(prefix="/diagramas", tags=["diagramas"])


def _obtener_proyecto_o_404(proyecto_id: int, db: Session) -> Proyecto:
    proyecto = db.query(Proyecto).filter(Proyecto.id == proyecto_id).first()
    if proyecto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El proyecto no existe.",
        )
    return proyecto


def _obtener_diagrama_o_404(diagrama_id: int, db: Session) -> Diagrama:
    diagrama = db.query(Diagrama).filter(Diagrama.id == diagrama_id).first()
    if diagrama is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El diagrama no existe.",
        )
    return diagrama


def _rol_de_usuario_en_proyecto(proyecto: Proyecto, usuario: Usuario, db: Session) -> str | None:
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


def _exigir_miembro(proyecto: Proyecto, usuario: Usuario, db: Session) -> None:
    if _rol_de_usuario_en_proyecto(proyecto, usuario, db) is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenés acceso a este proyecto.",
        )


@router.get("/proyecto/{proyecto_id}", response_model=DiagramaOut)
def obtener_diagrama_de_proyecto(
    proyecto_id: int,
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    proyecto = _obtener_proyecto_o_404(proyecto_id, db)
    _exigir_miembro(proyecto, usuario_actual, db)

    diagrama = db.query(Diagrama).filter(Diagrama.id_proyecto == proyecto_id).first()
    if diagrama is None:
        diagrama = Diagrama(
            id_proyecto=proyecto_id,
            nombre="Diagrama principal",
            contenido={"nodes": [], "edges": []},
        )
        db.add(diagrama)
        db.commit()
        db.refresh(diagrama)

    return diagrama


@router.get("/{diagrama_id}", response_model=DiagramaOut)
def obtener_diagrama(
    diagrama_id: int,
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    diagrama = _obtener_diagrama_o_404(diagrama_id, db)
    proyecto = _obtener_proyecto_o_404(diagrama.id_proyecto, db)
    _exigir_miembro(proyecto, usuario_actual, db)

    return diagrama


@router.put("/{diagrama_id}", response_model=DiagramaOut)
def actualizar_diagrama(
    diagrama_id: int,
    datos: DiagramaActualizar,
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    diagrama = _obtener_diagrama_o_404(diagrama_id, db)
    proyecto = _obtener_proyecto_o_404(diagrama.id_proyecto, db)
    _exigir_miembro(proyecto, usuario_actual, db)

    diagrama.contenido = datos.contenido
    db.commit()
    db.refresh(diagrama)

    return diagrama
