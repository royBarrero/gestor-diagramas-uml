"""Schemas Pydantic de la entidad Invitacion y de la lista de miembros de un proyecto."""

from pydantic import BaseModel


class InvitacionCrear(BaseModel):
    email: str


class InvitacionOut(BaseModel):
    id: int
    proyecto_id: int
    proyecto_nombre: str
    invitado_por: str

    class Config:
        from_attributes = True


class MiembroOut(BaseModel):
    id: int  # id del usuario
    nombre: str
    email: str
    rol: str
    es_creador: bool
