"""Schemas del chat grupal del proyecto (CU15)."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints

from app.models.mensaje_proyecto import MensajeProyecto


class MensajeCrear(BaseModel):
    texto: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class MensajeOut(BaseModel):
    id: int
    id_proyecto: int
    tipo: str  # "usuario" | "agente" | "sistema"
    texto: str
    autor_id: int | None = None
    autor_nombre: str | None = None
    destino_id: int | None = None
    destino_nombre: str | None = None
    # Id de la clase a la que se refiere una sugerencia del agente (CU16).
    elemento_referenciado: str | None = None
    created_at: datetime

    @classmethod
    def desde_modelo(cls, mensaje: MensajeProyecto) -> "MensajeOut":
        return cls(
            id=mensaje.id,
            id_proyecto=mensaje.id_proyecto,
            tipo=mensaje.tipo,
            texto=mensaje.texto,
            autor_id=mensaje.id_usuario,
            autor_nombre=mensaje.autor.nombre if mensaje.autor else None,
            destino_id=mensaje.id_usuario_destino,
            destino_nombre=mensaje.destino.nombre if mensaje.destino else None,
            elemento_referenciado=mensaje.elemento_referenciado,
            created_at=mensaje.created_at,
        )
