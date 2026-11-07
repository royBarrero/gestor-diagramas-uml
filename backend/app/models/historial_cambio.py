"""Modelo ORM del historial de cambios de un proyecto (CU18)."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class HistorialCambio(Base):
    __tablename__ = "historial_cambios"
    __table_args__ = (Index("ix_historial_cambios_proyecto_fecha", "id_proyecto", "created_at"),)

    id = Column(Integer, primary_key=True, index=True)
    id_proyecto = Column(Integer, ForeignKey("proyectos.id"), nullable=False)
    # Quien hizo el cambio o, si lo hizo el agente, quien se lo pidió.
    id_usuario = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    por_agente = Column(Boolean, nullable=False, default=False)
    origen = Column(String(20), nullable=False)  # manual/voz/foto/importacion/agente/deshacer
    tipo_operacion = Column(String(30), nullable=False)
    # Null en foto e importación, que no son sobre una clase. Sin clave foránea: la clase
    # vive en el JSON del diagrama, y su nombre se conserva por si después se elimina.
    id_elemento = Column(Text, nullable=True)
    nombre_elemento = Column(Text, nullable=True)
    detalle = Column(JSONB, nullable=False)
    resumen = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    proyecto = relationship("Proyecto", back_populates="historial")
    autor = relationship("Usuario")
