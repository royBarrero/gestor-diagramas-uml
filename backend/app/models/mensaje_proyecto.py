"""Modelo ORM de los mensajes del chat grupal de un proyecto (CU15)."""

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class MensajeProyecto(Base):
    __tablename__ = "mensajes_proyecto"
    __table_args__ = (Index("ix_mensajes_proyecto_proyecto_id", "id_proyecto", "id"),)

    id = Column(Integer, primary_key=True, index=True)
    id_proyecto = Column(Integer, ForeignKey("proyectos.id"), nullable=False)
    # Null en los mensajes del agente y del sistema, que no tienen usuario.
    id_usuario = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    tipo = Column(String(20), nullable=False, default="usuario")  # usuario/agente/sistema
    texto = Column(Text, nullable=False)
    # A quién le responde el agente.
    id_usuario_destino = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    # Id del nodo/clase al que se refiere el mensaje. Sin uso en CU15: la usa
    # CU16, y se crea ya porque create_tables.py no agrega columnas a tablas
    # existentes.
    elemento_referenciado = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    proyecto = relationship("Proyecto", back_populates="mensajes")
    autor = relationship("Usuario", foreign_keys=[id_usuario])
    destino = relationship("Usuario", foreign_keys=[id_usuario_destino])
