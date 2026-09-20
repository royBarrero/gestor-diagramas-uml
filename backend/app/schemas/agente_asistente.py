"""Schemas del agente asistente conversacional (CU13)."""

from typing import Literal

from pydantic import BaseModel


class MensajeChat(BaseModel):
    rol: Literal["usuario", "asistente"]
    texto: str


class PreguntaAsistenteIn(BaseModel):
    pregunta: str
    contexto_pantalla: str | None = None
    historial: list[MensajeChat] = []


class RespuestaAsistenteOut(BaseModel):
    estado: str  # "respondido" | "error_ia"
    respuesta: str | None = None
    mensaje: str | None = None
