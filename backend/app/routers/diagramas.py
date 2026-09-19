"""Router de diagramas. CU06: lectura y guardado del contenido del
diagrama de clases (nodos, atributos, métodos y relaciones). CU08: creación
de elementos del diagrama por comando de voz. CU09: digitalización de un
diagrama a partir de una fotografía. CU10: exportación e importación de
diagramas (JSON y XMI; la imagen es 100% client-side, ver useExportarImagen.js).
"""

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.permisos import exigir_miembro, obtener_proyecto_o_404
from app.models.diagrama import Diagrama
from app.models.usuario import Usuario
from app.realtime import sio
from app.schemas.comando_voz import ComandoVozOut
from app.schemas.diagrama import DiagramaActualizar, DiagramaOut
from app.schemas.digitalizacion import DigitalizacionOut
from app.schemas.exportacion import ImportacionOut
from app.services import comando_voz as servicio_voz
from app.services import digitalizacion_imagen as servicio_imagen
from app.services import exportacion_diagrama as servicio_exportacion
from app.services import xmi_diagrama as servicio_xmi
from app.services.ia_cliente import ServicioIANoDisponibleError

FORMATOS_EXPORTACION = "^(json|xmi)$"

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


@router.post("/{diagrama_id}/comando-voz", response_model=ComandoVozOut)
async def procesar_comando_voz(
    diagrama_id: int,
    audio: UploadFile = File(...),
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    diagrama = _obtener_diagrama_o_404(diagrama_id, db)
    proyecto = obtener_proyecto_o_404(diagrama.id_proyecto, db)
    exigir_miembro(proyecto, usuario_actual, db)

    if not audio.content_type or not audio.content_type.startswith("audio/"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El archivo enviado no es de audio.")

    audio_bytes = await audio.read()

    try:
        texto = servicio_voz.transcribir_audio(audio_bytes, audio.filename or "comando.webm")
        accion = servicio_voz.interpretar_comando(texto, diagrama.contenido.get("nodes", []))
    except servicio_voz.ServicioIANoDisponibleError as exc:
        return ComandoVozOut(estado="error_ia", mensaje=str(exc))

    try:
        nuevo_contenido = servicio_voz.aplicar_accion(diagrama.contenido, accion)
    except servicio_voz.ComandoNoInterpretadoError as exc:
        return ComandoVozOut(estado="no_entendido", mensaje=str(exc), transcripcion=texto)

    diagrama.contenido = nuevo_contenido
    db.commit()
    db.refresh(diagrama)

    await sio.emit("cambio_diagrama", nuevo_contenido, room=f"diagrama_{diagrama_id}")

    return ComandoVozOut(estado="aplicado", mensaje="Comando aplicado.", contenido=nuevo_contenido, transcripcion=texto)


@router.post("/{diagrama_id}/digitalizar-imagen", response_model=DigitalizacionOut)
async def digitalizar_imagen(
    diagrama_id: int,
    imagen: UploadFile = File(...),
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    diagrama = _obtener_diagrama_o_404(diagrama_id, db)
    proyecto = obtener_proyecto_o_404(diagrama.id_proyecto, db)
    exigir_miembro(proyecto, usuario_actual, db)

    if not imagen.content_type or not imagen.content_type.startswith("image/"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El archivo enviado no es una imagen.")

    imagen_bytes = await imagen.read()

    try:
        resultado = servicio_imagen.interpretar_imagen(imagen_bytes, imagen.content_type)
    except ServicioIANoDisponibleError as exc:
        return DigitalizacionOut(estado="error_ia", mensaje=str(exc))

    clases = resultado.get("clases") or []
    relaciones = resultado.get("relaciones") or []

    if not clases:
        mensaje = resultado.get("advertencia") or "No se pudo reconocer ningún elemento en la imagen."
        return DigitalizacionOut(estado="fallido", mensaje=mensaje)

    nuevo_contenido, relaciones_omitidas = servicio_imagen.construir_contenido(diagrama.contenido, resultado)

    diagrama.contenido = nuevo_contenido
    db.commit()
    db.refresh(diagrama)

    await sio.emit("cambio_diagrama", nuevo_contenido, room=f"diagrama_{diagrama_id}")

    advertencia = resultado.get("advertencia")
    if relaciones_omitidas:
        detalle = f"No se pudieron aplicar estas relaciones (no se encontró alguna de las clases): {'; '.join(relaciones_omitidas)}."
        advertencia = f"{advertencia} {detalle}" if advertencia else detalle

    es_confiable = resultado.get("confianza") == "alta" and not advertencia
    estado = "aplicado" if es_confiable else "parcial"
    mensaje = (
        "Diagrama digitalizado."
        if estado == "aplicado"
        else advertencia or "Revisá el diagrama: algunos elementos pueden no haberse reconocido bien."
    )

    return DigitalizacionOut(
        estado=estado,
        mensaje=mensaje,
        contenido=nuevo_contenido,
        clases_reconocidas=len(clases),
        relaciones_reconocidas=len(relaciones),
    )


@router.get("/{diagrama_id}/exportar")
def exportar_diagrama(
    diagrama_id: int,
    formato: str = Query(..., pattern=FORMATOS_EXPORTACION),
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    diagrama = _obtener_diagrama_o_404(diagrama_id, db)
    proyecto = obtener_proyecto_o_404(diagrama.id_proyecto, db)
    exigir_miembro(proyecto, usuario_actual, db)

    nombre_archivo = servicio_exportacion.nombre_archivo_descarga(diagrama.nombre, formato)

    if formato == "xmi":
        try:
            contenido_str = servicio_xmi.contenido_a_xmi(diagrama.contenido, diagrama.nombre)
        except servicio_exportacion.ArchivoInvalidoError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
        media_type = "application/xml"
    else:
        contenido_str = json.dumps(diagrama.contenido, ensure_ascii=False, indent=2)
        media_type = "application/json"

    return Response(
        content=contenido_str,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )


@router.post("/{diagrama_id}/importar", response_model=ImportacionOut)
async def importar_diagrama(
    diagrama_id: int,
    formato: str = Form(..., pattern=FORMATOS_EXPORTACION),
    archivo: UploadFile = File(...),
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    diagrama = _obtener_diagrama_o_404(diagrama_id, db)
    proyecto = obtener_proyecto_o_404(diagrama.id_proyecto, db)
    exigir_miembro(proyecto, usuario_actual, db)

    archivo_bytes = await archivo.read()
    if not archivo_bytes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El archivo está vacío.")

    try:
        if formato == "xmi":
            nuevo_contenido = servicio_xmi.xmi_a_contenido(archivo_bytes)
        else:
            nuevo_contenido = servicio_exportacion.contenido_desde_json(archivo_bytes)
    except servicio_exportacion.ArchivoInvalidoError as exc:
        return ImportacionOut(estado="formato_invalido", mensaje=str(exc))

    diagrama.contenido = nuevo_contenido
    db.commit()
    db.refresh(diagrama)

    await sio.emit("cambio_diagrama", nuevo_contenido, room=f"diagrama_{diagrama_id}")

    return ImportacionOut(estado="aplicado", mensaje="Diagrama importado correctamente.", contenido=nuevo_contenido)
