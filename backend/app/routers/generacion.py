"""Router de generación de código a partir del diagrama de clases de un
proyecto. Exclusivo del administrador del proyecto.

CU11: backend Spring Boot. CU12: frontend Flutter, que exige que el backend
se haya generado con éxito al menos una vez (`Proyecto.backend_generado_en`)
— ver docstring de `modelo_backend.py` sobre por qué esa marca no se invalida
si el diagrama cambia después.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.permisos import exigir_administrador, obtener_proyecto_o_404
from app.models.diagrama import Diagrama
from app.models.usuario import Usuario
from app.services import generacion_backend as servicio_backend
from app.services import generacion_frontend as servicio_frontend
from app.services.modelo_backend import GeneracionInvalidaError

router = APIRouter(prefix="/proyectos", tags=["generacion"])


def _contenido_diagrama(proyecto_id: int, db: Session) -> dict:
    diagrama = db.query(Diagrama).filter(Diagrama.id_proyecto == proyecto_id).first()
    return diagrama.contenido if diagrama else {"nodes": [], "edges": []}


def _respuesta_zip(zip_bytes: bytes, nombre_archivo: str) -> Response:
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )


@router.get("/{proyecto_id}/generar-backend")
def generar_backend(
    proyecto_id: int,
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    proyecto = obtener_proyecto_o_404(proyecto_id, db)
    exigir_administrador(proyecto, usuario_actual, db)

    contenido = _contenido_diagrama(proyecto_id, db)

    try:
        zip_bytes = servicio_backend.generar_zip_backend(contenido, proyecto.nombre)
    except GeneracionInvalidaError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    proyecto.backend_generado_en = datetime.now(timezone.utc)
    db.commit()

    return _respuesta_zip(zip_bytes, servicio_backend.nombre_zip_backend(proyecto.nombre))


@router.get("/{proyecto_id}/generar-frontend")
def generar_frontend(
    proyecto_id: int,
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    proyecto = obtener_proyecto_o_404(proyecto_id, db)
    exigir_administrador(proyecto, usuario_actual, db)

    if proyecto.backend_generado_en is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Primero tenés que generar el backend de este proyecto.",
        )

    contenido = _contenido_diagrama(proyecto_id, db)

    try:
        zip_bytes = servicio_frontend.generar_zip_frontend(contenido, proyecto.nombre)
    except GeneracionInvalidaError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    return _respuesta_zip(zip_bytes, servicio_frontend.nombre_zip_frontend(proyecto.nombre))
