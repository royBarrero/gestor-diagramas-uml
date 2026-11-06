"""Modelo ORM de los cambios que el agente de IA hace a pedido de un integrante
(CU17): lo pedido, en qué estado está y la copia para poder deshacerlo."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class AccionAgente(Base):
    __tablename__ = "acciones_agente"

    id = Column(Integer, primary_key=True, index=True)
    id_proyecto = Column(Integer, ForeignKey("proyectos.id"), nullable=False, index=True)
    id_solicitante = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    # El mensaje del chat que lleva los botones de esta acción.
    id_mensaje = Column(Integer, ForeignKey("mensajes_proyecto.id"), nullable=True, index=True)
    # La sugerencia de CU16 que resuelve, si vino de "Pedir corrección".
    id_sugerencia = Column(Integer, ForeignKey("mensajes_proyecto.id"), nullable=True, index=True)
    estado = Column(String(20), nullable=False)  # pendiente/confirmada/cancelada/aplicada/deshecha
    operaciones = Column(JSONB, nullable=False)
    # Solo en las aplicadas: el diagrama antes del cambio y la huella de cómo quedó.
    copia_contenido = Column(JSONB, nullable=True)
    huella_resultante = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    proyecto = relationship("Proyecto", back_populates="acciones_agente")
