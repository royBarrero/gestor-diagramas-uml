"""Router de invitaciones desde la perspectiva del usuario invitado."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.invitacion import Invitacion
from app.models.miembro_proyecto import MiembroProyecto
from app.models.proyecto import Proyecto
from app.models.usuario import Usuario
from app.realtime import room_usuario, sio
from app.schemas.invitacion import InvitacionOut

router = APIRouter(prefix="/invitaciones", tags=["invitaciones"])


def _obtener_invitacion_propia_o_404(
    invitacion_id: int, usuario_actual: Usuario, db: Session
) -> Invitacion:
    invitacion = (
        db.query(Invitacion)
        .filter(
            Invitacion.id == invitacion_id,
            Invitacion.id_usuario_invitado == usuario_actual.id,
        )
        .first()
    )
    if invitacion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La invitación no existe.",
        )
    return invitacion


@router.get("/pendientes", response_model=list[InvitacionOut])
def listar_pendientes(
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filas = (
        db.query(Invitacion, Proyecto, Usuario)
        .join(Proyecto, Proyecto.id == Invitacion.id_proyecto)
        .join(Usuario, Usuario.id == Invitacion.id_usuario_invita)
        .filter(
            Invitacion.id_usuario_invitado == usuario_actual.id,
            Invitacion.estado == "pendiente",
        )
        .all()
    )

    return [
        InvitacionOut(
            id=invitacion.id,
            proyecto_id=proyecto.id,
            proyecto_nombre=proyecto.nombre,
            invitado_por=invitador.nombre,
        )
        for invitacion, proyecto, invitador in filas
    ]


@router.post("/{invitacion_id}/aceptar", status_code=status.HTTP_204_NO_CONTENT)
async def aceptar_invitacion(
    invitacion_id: int,
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    invitacion = _obtener_invitacion_propia_o_404(invitacion_id, usuario_actual, db)
    id_proyecto = invitacion.id_proyecto

    ya_es_miembro = (
        db.query(MiembroProyecto)
        .filter(
            MiembroProyecto.id_proyecto == id_proyecto,
            MiembroProyecto.id_usuario == usuario_actual.id,
        )
        .first()
    )
    if ya_es_miembro is None:
        db.add(
            MiembroProyecto(
                id_proyecto=id_proyecto,
                id_usuario=usuario_actual.id,
                rol="colaborador",
            )
        )

    db.delete(invitacion)
    db.commit()

    ids_miembros = [
        fila[0]
        for fila in db.query(MiembroProyecto.id_usuario)
        .filter(MiembroProyecto.id_proyecto == id_proyecto)
        .all()
    ]
    for id_usuario in ids_miembros:
        await sio.emit(
            "miembro_agregado",
            {"proyecto_id": id_proyecto, "total_miembros": len(ids_miembros)},
            room=room_usuario(id_usuario),
        )


@router.post("/{invitacion_id}/rechazar", status_code=status.HTTP_204_NO_CONTENT)
def rechazar_invitacion(
    invitacion_id: int,
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    invitacion = _obtener_invitacion_propia_o_404(invitacion_id, usuario_actual, db)
    db.delete(invitacion)
    db.commit()
