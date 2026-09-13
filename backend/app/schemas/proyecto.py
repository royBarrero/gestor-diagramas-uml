"""Schemas Pydantic de la entidad Proyecto."""

from pydantic import BaseModel


class ProyectoCrear(BaseModel):
    nombre: str
    descripcion: str | None = None


class ProyectoEditar(BaseModel):
    nombre: str
    descripcion: str | None = None


class ProyectoConRolOut(BaseModel):
    id: int
    nombre: str
    descripcion: str | None
    rol: str  # "administrador" | "colaborador"
    total_miembros: int

    class Config:
        from_attributes = True
