"""Router del historial de cambios de un proyecto (CU18). Lo usan la pizarra y la app
móvil (CU19). Las entradas nuevas llegan además por el socket del proyecto."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.permisos import exigir_miembro, obtener_proyecto_o_404
from app.models.historial_cambio import HistorialCambio
from app.models.usuario import Usuario
from app.schemas.historial_cambio import (
    ClaseFiltro,
    FiltrosHistorialOut,
    HistorialOut,
    IntegranteFiltro,
    color_de_usuario,
)

router = APIRouter(prefix="/proyectos/{proyecto_id}/historial", tags=["historial"])


@router.get("", response_model=list[HistorialOut])
def listar_historial(
    proyecto_id: int,
    usuario_id: int | None = None,
    clase_id: str | None = None,
    antes_de: int | None = None,
    limite: int = Query(50, ge=1, le=200),
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Del más reciente al más antiguo. `antes_de` es el id de la última entrada ya
    cargada. `clase_id` también trae las relaciones de esa clase, que están registradas
    en la otra clase de la relación."""
    proyecto = obtener_proyecto_o_404(proyecto_id, db)
    exigir_miembro(proyecto, usuario_actual, db)

    consulta = (
        db.query(HistorialCambio)
        .options(joinedload(HistorialCambio.autor))
        .filter(HistorialCambio.id_proyecto == proyecto_id)
    )
    if usuario_id is not None:
        consulta = consulta.filter(HistorialCambio.id_usuario == usuario_id)
    if clase_id is not None:
        consulta = consulta.filter(
            or_(HistorialCambio.id_elemento == clase_id, HistorialCambio.detalle["ids_clases"].contains([clase_id]))
        )
    if antes_de is not None:
        consulta = consulta.filter(HistorialCambio.id < antes_de)

    entradas = consulta.order_by(HistorialCambio.created_at.desc(), HistorialCambio.id.desc()).limit(limite).all()
    return [HistorialOut.desde_modelo(e) for e in entradas]


@router.get("/filtros", response_model=FiltrosHistorialOut)
def filtros_historial(
    proyecto_id: int,
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Incluye a quien ya salió del proyecto y a las clases eliminadas, con su último nombre."""
    proyecto = obtener_proyecto_o_404(proyecto_id, db)
    exigir_miembro(proyecto, usuario_actual, db)

    integrantes = (
        db.query(Usuario.id, Usuario.nombre)
        .join(HistorialCambio, HistorialCambio.id_usuario == Usuario.id)
        .filter(HistorialCambio.id_proyecto == proyecto_id)
        .distinct()
        .order_by(Usuario.nombre)
        .all()
    )
    clases = (
        db.query(HistorialCambio.id_elemento, HistorialCambio.nombre_elemento)
        .filter(HistorialCambio.id_proyecto == proyecto_id, HistorialCambio.id_elemento.isnot(None))
        .distinct(HistorialCambio.id_elemento)
        .order_by(HistorialCambio.id_elemento, HistorialCambio.id.desc())
        .all()
    )
    return FiltrosHistorialOut(
        integrantes=[IntegranteFiltro(id=i.id, nombre=i.nombre, color=color_de_usuario(i.id)) for i in integrantes],
        clases=sorted(
            (ClaseFiltro(id=c.id_elemento, nombre=c.nombre_elemento or "") for c in clases),
            key=lambda c: c.nombre.lower(),
        ),
    )
