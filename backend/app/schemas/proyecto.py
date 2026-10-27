"""Schemas Pydantic de la entidad Proyecto."""

from datetime import datetime

from pydantic import BaseModel


class ProyectoCrear(BaseModel):
    nombre: str
    descripcion: str | None = None


class ProyectoEditar(BaseModel):
    nombre: str
    descripcion: str | None = None


class MiembroResumenOut(BaseModel):
    id: int
    nombre: str


class ProyectoConRolOut(BaseModel):
    id: int
    nombre: str
    descripcion: str | None
    rol: str  # "administrador" | "colaborador"
    total_miembros: int
    # Resumen del diagrama y miembros para las tarjetas del listado.
    total_clases: int = 0
    total_relaciones: int = 0
    updated_at: datetime | None = None
    miembros: list[MiembroResumenOut] = []
    # CU12: el frontend solo se puede generar si el backend ya se generó.
    backend_generado_en: datetime | None = None

    class Config:
        from_attributes = True
