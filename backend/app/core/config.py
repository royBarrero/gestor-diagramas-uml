"""Configuración compartida leída desde variables de entorno / backend/.env."""

import os
import re
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


def get_cors_origins() -> list[str]:
    """Orígenes permitidos para CORS (FastAPI) y Socket.IO, separados por coma en CORS_ORIGINS."""
    raw = os.getenv("CORS_ORIGINS", "http://localhost:5173")
    return [origen.strip() for origen in raw.split(",") if origen.strip()]


# En desarrollo se acepta cualquier puerto de localhost / 127.0.0.1, porque
# `flutter run -d chrome` abre la app móvil (CU19) en un puerto aleatorio.
_REGEX_LOCALHOST = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"


def get_cors_origin_regex() -> str | None:
    """Regex extra de orígenes permitidos; solo con ENVIRONMENT=development."""
    if os.getenv("ENVIRONMENT", "production") == "development":
        return _REGEX_LOCALHOST
    return None


def origen_permitido(origen: str | None) -> bool:
    """Misma regla que el CORS de FastAPI, para usar en Socket.IO."""
    if not origen:
        return False
    if origen in get_cors_origins():
        return True
    regex = get_cors_origin_regex()
    return bool(regex and re.match(regex, origen))
