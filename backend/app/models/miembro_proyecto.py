"""Modelo ORM de la entidad MiembroProyecto.

Tabla intermedia entre Usuario y Proyecto que guarda el rol
(administrador / colaborador) de cada usuario dentro de un proyecto.
"""

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class MiembroProyecto(Base):
    __tablename__ = "miembros_proyecto"
    __table_args__ = (
        UniqueConstraint("id_proyecto", "id_usuario", name="uq_miembro_proyecto_usuario"),
    )

    id = Column(Integer, primary_key=True, index=True)
    id_proyecto = Column(Integer, ForeignKey("proyectos.id"), nullable=False, index=True)
    id_usuario = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    rol = Column(String(20), nullable=False)  # "administrador" / "colaborador"
    fecha_union = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    proyecto = relationship("Proyecto", back_populates="miembros")
    usuario = relationship("Usuario", back_populates="membresias")
