"""Configuración compartida leída desde variables de entorno / backend/.env."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


def get_cors_origins() -> list[str]:
    """Orígenes permitidos para CORS (FastAPI) y Socket.IO, separados por coma en CORS_ORIGINS."""
    raw = os.getenv("CORS_ORIGINS", "http://localhost:5173")
    return [origen.strip() for origen in raw.split(",") if origen.strip()]
