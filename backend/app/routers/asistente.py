"""Router del agente asistente conversacional (CU13). A diferencia de
comando-voz/digitalizar-imagen (colgados del router de `diagramas`), este no
depende de ningún proyecto/diagrama puntual — solo requiere sesión activa.
"""

from fastapi import APIRouter, Depends

from app.core.deps import get_current_user
from app.models.usuario import Usuario
from app.schemas.agente_asistente import PreguntaAsistenteIn, RespuestaAsistenteOut
from app.services import agente_asistente as servicio_asistente
from app.services.ia_cliente import ServicioIANoDisponibleError

router = APIRouter(prefix="/asistente", tags=["asistente"])


@router.post("/preguntar", response_model=RespuestaAsistenteOut)
def preguntar(
    payload: PreguntaAsistenteIn,
    usuario_actual: Usuario = Depends(get_current_user),
):
    try:
        respuesta = servicio_asistente.responder_pregunta(
            payload.pregunta,
            payload.contexto_pantalla,
            [turno.model_dump() for turno in payload.historial],
        )
    except ServicioIANoDisponibleError as exc:
        return RespuestaAsistenteOut(estado="error_ia", mensaje=str(exc))

    return RespuestaAsistenteOut(estado="respondido", respuesta=respuesta)
