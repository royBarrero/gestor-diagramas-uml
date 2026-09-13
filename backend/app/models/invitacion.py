"""Modelo ORM de la entidad Invitacion (invitación a un proyecto)."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Invitacion(Base):
    __tablename__ = "invitaciones"

    id = Column(Integer, primary_key=True, index=True)
    id_proyecto = Column(Integer, ForeignKey("proyectos.id"), nullable=False, index=True)
    id_usuario_invitado = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    id_usuario_invita = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    estado = Column(String(20), nullable=False, default="pendiente")  # pendiente/aceptada/rechazada
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    proyecto = relationship("Proyecto")
    invitado = relationship("Usuario", foreign_keys=[id_usuario_invitado])
    invitador = relationship("Usuario", foreign_keys=[id_usuario_invita])
