"""Schemas del historial de cambios (CU18). Lo usan la pizarra y la app móvil (CU19):
cada entrada trae todo lo que hace falta para mostrarla, sin consultas extra."""

from datetime import datetime

from pydantic import BaseModel

from app.models.historial_cambio import HistorialCambio

# La misma paleta y el mismo cálculo que colorPorUsuario, en frontend/src/utils/avatar.js.
PALETA_COLABORADORES = ("#4c8dff", "#e0a030", "#33b679", "#e05c5c", "#a06ce0", "#3fbfbf")


def color_de_usuario(usuario_id: int) -> str:
    return PALETA_COLABORADORES[usuario_id % len(PALETA_COLABORADORES)]


class HistorialOut(BaseModel):
    id: int
    id_proyecto: int
    autor_id: int
    autor_nombre: str
    autor_color: str
    por_agente: bool
    origen: str  # "manual" | "voz" | "foto" | "importacion" | "agente" | "deshacer"
    tipo_operacion: str
    id_elemento: str | None = None
    nombre_elemento: str | None = None
    resumen: str
    # Las clases involucradas: alcanza para aplicar el filtro por clase a lo que llega en vivo.
    ids_clases: list[str] = []
    created_at: datetime

    @classmethod
    def desde_modelo(cls, entrada: HistorialCambio) -> "HistorialOut":
        return cls(
            id=entrada.id,
            id_proyecto=entrada.id_proyecto,
            autor_id=entrada.id_usuario,
            autor_nombre=entrada.autor.nombre,
            autor_color=color_de_usuario(entrada.id_usuario),
            por_agente=entrada.por_agente,
            origen=entrada.origen,
            tipo_operacion=entrada.tipo_operacion,
            id_elemento=entrada.id_elemento,
            nombre_elemento=entrada.nombre_elemento,
            resumen=entrada.resumen,
            ids_clases=(entrada.detalle or {}).get("ids_clases") or [],
            created_at=entrada.created_at,
        )


class IntegranteFiltro(BaseModel):
    id: int
    nombre: str
    color: str


class ClaseFiltro(BaseModel):
    id: str
    nombre: str


class FiltrosHistorialOut(BaseModel):
    """Quiénes y qué clases aparecen en el historial, aunque ya no estén en el proyecto."""

    integrantes: list[IntegranteFiltro]
    clases: list[ClaseFiltro]
