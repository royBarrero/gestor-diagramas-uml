"""Schema de respuesta del endpoint de comando de voz (CU08)."""

from pydantic import BaseModel


class ComandoVozOut(BaseModel):
    estado: str  # "aplicado" | "no_entendido" | "error_ia"
    mensaje: str
    contenido: dict | None = None
    transcripcion: str | None = None
