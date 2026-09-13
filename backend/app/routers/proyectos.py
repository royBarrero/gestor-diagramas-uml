"""Router de proyectos. CU03: listado de "mis proyectos" (solo lectura).
CU04: CRUD completo de proyectos, con validación de rol de administrador
para editar/eliminar.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.invitacion import Invitacion
from app.models.miembro_proyecto import MiembroProyecto
from app.models.proyecto import Proyecto
from app.models.usuario import Usuario
from app.schemas.invitacion import InvitacionCrear, MiembroOut
from app.schemas.proyecto import ProyectoConRolOut, ProyectoCrear, ProyectoEditar

router = APIRouter(prefix="/proyectos", tags=["proyectos"])


def _obtener_proyecto_o_404(proyecto_id: int, db: Session) -> Proyecto:
    proyecto = db.query(Proyecto).filter(Proyecto.id == proyecto_id).first()
    if proyecto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El proyecto no existe.",
        )
    return proyecto


def _rol_de_usuario_en_proyecto(proyecto: Proyecto, usuario: Usuario, db: Session) -> str | None:
    """Rol del usuario en el proyecto, o None si no es miembro.

    Fallback: si es el creador del proyecto pero no tiene fila propia en
    miembros_proyecto (dato viejo/de prueba, previo a que POST /proyectos
    creara esa fila automáticamente), se lo trata como administrador.
    """
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


def _exigir_administrador(proyecto: Proyecto, usuario: Usuario, db: Session) -> None:
    if _rol_de_usuario_en_proyecto(proyecto, usuario, db) != "administrador":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el administrador del proyecto puede realizar esta acción.",
        )


def _contar_miembros(proyecto_id: int, db: Session) -> int:
    total = (
        db.query(func.count(MiembroProyecto.id))
        .filter(MiembroProyecto.id_proyecto == proyecto_id)
        .scalar()
    )
    return total or 1


@router.get("/mis-proyectos", response_model=list[ProyectoConRolOut])
def listar_mis_proyectos(
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filas = (
        db.query(
            Proyecto.id,
            Proyecto.nombre,
            Proyecto.descripcion,
            MiembroProyecto.rol,
        )
        .outerjoin(
            MiembroProyecto,
            (MiembroProyecto.id_proyecto == Proyecto.id)
            & (MiembroProyecto.id_usuario == usuario_actual.id),
        )
        .filter(
            or_(
                MiembroProyecto.id_usuario == usuario_actual.id,
                Proyecto.id_usuario_creador == usuario_actual.id,
            )
        )
        .all()
    )

    ids_proyectos = [fila.id for fila in filas]
    conteos = (
        dict(
            db.query(MiembroProyecto.id_proyecto, func.count(MiembroProyecto.id))
            .filter(MiembroProyecto.id_proyecto.in_(ids_proyectos))
            .group_by(MiembroProyecto.id_proyecto)
            .all()
        )
        if ids_proyectos
        else {}
    )

    return [
        ProyectoConRolOut(
            id=fila.id,
            nombre=fila.nombre,
            descripcion=fila.descripcion,
            rol=fila.rol or "administrador",
            total_miembros=conteos.get(fila.id) or 1,
        )
        for fila in filas
    ]


@router.post("", response_model=ProyectoConRolOut, status_code=status.HTTP_201_CREATED)
def crear_proyecto(
    datos: ProyectoCrear,
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    nuevo_proyecto = Proyecto(
        nombre=datos.nombre,
        descripcion=datos.descripcion,
        id_usuario_creador=usuario_actual.id,
    )
    db.add(nuevo_proyecto)
    db.flush()

    db.add(
        MiembroProyecto(
            id_proyecto=nuevo_proyecto.id,
            id_usuario=usuario_actual.id,
            rol="administrador",
        )
    )
    db.commit()
    db.refresh(nuevo_proyecto)

    return ProyectoConRolOut(
        id=nuevo_proyecto.id,
        nombre=nuevo_proyecto.nombre,
        descripcion=nuevo_proyecto.descripcion,
        rol="administrador",
        total_miembros=1,
    )


@router.put("/{proyecto_id}", response_model=ProyectoConRolOut)
def editar_proyecto(
    proyecto_id: int,
    datos: ProyectoEditar,
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    proyecto = _obtener_proyecto_o_404(proyecto_id, db)
    _exigir_administrador(proyecto, usuario_actual, db)

    proyecto.nombre = datos.nombre
    proyecto.descripcion = datos.descripcion
    db.commit()
    db.refresh(proyecto)

    return ProyectoConRolOut(
        id=proyecto.id,
        nombre=proyecto.nombre,
        descripcion=proyecto.descripcion,
        rol="administrador",
        total_miembros=_contar_miembros(proyecto.id, db),
    )


@router.delete("/{proyecto_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_proyecto(
    proyecto_id: int,
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    proyecto = _obtener_proyecto_o_404(proyecto_id, db)
    _exigir_administrador(proyecto, usuario_actual, db)

    db.delete(proyecto)
    db.commit()


@router.get("/{proyecto_id}/miembros", response_model=list[MiembroOut])
def listar_miembros(
    proyecto_id: int,
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    proyecto = _obtener_proyecto_o_404(proyecto_id, db)
    _exigir_administrador(proyecto, usuario_actual, db)

    filas = (
        db.query(MiembroProyecto, Usuario)
        .join(Usuario, Usuario.id == MiembroProyecto.id_usuario)
        .filter(MiembroProyecto.id_proyecto == proyecto_id)
        .all()
    )

    return [
        MiembroOut(
            id=usuario.id,
            nombre=usuario.nombre,
            email=usuario.email,
            rol=membresia.rol,
            es_creador=usuario.id == proyecto.id_usuario_creador,
        )
        for membresia, usuario in filas
    ]


@router.post("/{proyecto_id}/invitaciones", status_code=status.HTTP_201_CREATED)
def invitar_miembro(
    proyecto_id: int,
    datos: InvitacionCrear,
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    proyecto = _obtener_proyecto_o_404(proyecto_id, db)
    _exigir_administrador(proyecto, usuario_actual, db)

    usuario_invitado = db.query(Usuario).filter(Usuario.email == datos.email).first()
    if usuario_invitado is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    if _rol_de_usuario_en_proyecto(proyecto, usuario_invitado, db) is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario ya es miembro del proyecto.",
        )

    invitacion_existente = (
        db.query(Invitacion)
        .filter(
            Invitacion.id_proyecto == proyecto_id,
            Invitacion.id_usuario_invitado == usuario_invitado.id,
            Invitacion.estado == "pendiente",
        )
        .first()
    )
    if invitacion_existente is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe una invitación pendiente para este usuario.",
        )

    db.add(
        Invitacion(
            id_proyecto=proyecto_id,
            id_usuario_invitado=usuario_invitado.id,
            id_usuario_invita=usuario_actual.id,
            estado="pendiente",
        )
    )
    db.commit()

    return {"mensaje": "Invitación enviada."}


@router.delete("/{proyecto_id}/miembros/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def quitar_miembro(
    proyecto_id: int,
    usuario_id: int,
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    proyecto = _obtener_proyecto_o_404(proyecto_id, db)
    _exigir_administrador(proyecto, usuario_actual, db)

    if usuario_id == proyecto.id_usuario_creador:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede quitar al creador del proyecto.",
        )

    membresia = (
        db.query(MiembroProyecto)
        .filter(
            MiembroProyecto.id_proyecto == proyecto_id,
            MiembroProyecto.id_usuario == usuario_id,
        )
        .first()
    )
    if membresia is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El usuario no es miembro de este proyecto.",
        )

    db.delete(membresia)
    db.commit()
