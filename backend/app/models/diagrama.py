"""Modelo ORM de la entidad Diagrama.

El campo `contenido` guarda en JSONB la estructura del diagrama de clases
(nodos, atributos, métodos y relaciones) tal como la maneja React Flow.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Diagrama(Base):
    __tablename__ = "diagramas"

    id = Column(Integer, primary_key=True, index=True)
    id_proyecto = Column(Integer, ForeignKey("proyectos.id"), nullable=False, index=True)
    nombre = Column(String(150), nullable=False)
    contenido = Column(JSONB, nullable=True, default=dict)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    proyecto = relationship("Proyecto", back_populates="diagramas")
