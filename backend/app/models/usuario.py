"""Modelo ORM de la entidad Usuario."""

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(120), nullable=False)
    email = Column(String(180), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Proyectos que este usuario creó (es el administrador dueño)
    proyectos_creados = relationship("Proyecto", back_populates="creador")
    # Membresías de este usuario en proyectos (propios o ajenos)
    membresias = relationship("MiembroProyecto", back_populates="usuario")
