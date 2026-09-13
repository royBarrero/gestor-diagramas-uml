"""Schemas Pydantic de la entidad Usuario."""

from datetime import datetime

from pydantic import BaseModel


class UsuarioRegistro(BaseModel):
    nombre: str
    email: str
    password: str


class UsuarioOut(BaseModel):
    id: int
    nombre: str
    email: str
    created_at: datetime

    class Config:
        from_attributes = True
