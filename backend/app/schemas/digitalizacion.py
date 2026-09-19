"""Schema de respuesta del endpoint de digitalización por foto (CU09)."""

from pydantic import BaseModel


class DigitalizacionOut(BaseModel):
    estado: str  # "aplicado" | "parcial" | "fallido" | "error_ia"
    mensaje: str
    contenido: dict | None = None
    clases_reconocidas: int = 0
    relaciones_reconocidas: int = 0
