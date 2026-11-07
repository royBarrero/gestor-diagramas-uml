"""Modelos ORM del sistema.

Importar este paquete (`import app.models`) registra todos los modelos
en `Base.metadata`, necesario para crear las tablas o generar migraciones.
"""

from app.models.accion_agente import AccionAgente
from app.models.diagrama import Diagrama
from app.models.historial_cambio import HistorialCambio
from app.models.invitacion import Invitacion
from app.models.mensaje_proyecto import MensajeProyecto
from app.models.miembro_proyecto import MiembroProyecto
from app.models.proyecto import Proyecto
from app.models.usuario import Usuario

__all__ = ["Usuario", "Proyecto", "MiembroProyecto", "Diagrama", "Invitacion", "MensajeProyecto", "AccionAgente", "HistorialCambio"]
