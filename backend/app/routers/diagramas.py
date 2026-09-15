"""Router de diagramas. CU06: lectura y guardado del contenido del
diagrama de clases (nodos, atributos, métodos y relaciones).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.permisos import exigir_miembro, obtener_proyecto_o_404
from app.models.diagrama import Diagrama
from app.models.usuario import Usuario
from app.schemas.diagrama import DiagramaActualizar, DiagramaOut

router = APIRouter(prefix="/diagramas", tags=["diagramas"])


def _obtener_diagrama_o_404(diagrama_id: int, db: Session) -> Diagrama:
    diagrama = db.query(Diagrama).filter(Diagrama.id == diagrama_id).first()
    if diagrama is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El diagrama no existe.",
        )
    return diagrama


@router.get("/proyecto/{proyecto_id}", response_model=DiagramaOut)
def obtener_diagrama_de_proyecto(
    proyecto_id: int,
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    proyecto = obtener_proyecto_o_404(proyecto_id, db)
    exigir_miembro(proyecto, usuario_actual, db)

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
    proyecto = obtener_proyecto_o_404(diagrama.id_proyecto, db)
    exigir_miembro(proyecto, usuario_actual, db)

    return diagrama


@router.put("/{diagrama_id}", response_model=DiagramaOut)
def actualizar_diagrama(
    diagrama_id: int,
    datos: DiagramaActualizar,
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    diagrama = _obtener_diagrama_o_404(diagrama_id, db)
    proyecto = obtener_proyecto_o_404(diagrama.id_proyecto, db)
    exigir_miembro(proyecto, usuario_actual, db)

    diagrama.contenido = datos.contenido
    db.commit()
    db.refresh(diagrama)

    return diagrama
