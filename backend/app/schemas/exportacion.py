"""Schema de respuesta de la importación de diagramas (CU10)."""

from pydantic import BaseModel


class ImportacionOut(BaseModel):
    estado: str  # "aplicado" | "formato_invalido"
    mensaje: str
    contenido: dict | None = None
