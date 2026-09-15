"""Schemas Pydantic de la entidad Diagrama."""

from datetime import datetime

from pydantic import BaseModel


class DiagramaActualizar(BaseModel):
    contenido: dict


class DiagramaOut(BaseModel):
    id: int
    id_proyecto: int
    nombre: str
    contenido: dict
    updated_at: datetime

    class Config:
        from_attributes = True
