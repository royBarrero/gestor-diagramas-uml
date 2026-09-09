"""Modelo ORM de la entidad Proyecto."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Proyecto(Base):
    __tablename__ = "proyectos"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(150), nullable=False)
    descripcion = Column(Text, nullable=True)
    id_usuario_creador = Column(
        Integer, ForeignKey("usuarios.id"), nullable=False, index=True
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    creador = relationship("Usuario", back_populates="proyectos_creados")
    miembros = relationship(
        "MiembroProyecto", back_populates="proyecto", cascade="all, delete-orphan"
    )
    diagramas = relationship(
        "Diagrama", back_populates="proyecto", cascade="all, delete-orphan"
    )
