"""Bootstrap compartido del cliente de OpenAI, usado por CU08 (comando_voz)
y CU09 (digitalizacion_imagen). Aislado acá para que ninguno de los dos
dependa de que la API key esté configurada al momento de importar el módulo
(el backend debe poder bootear sin OPENAI_API_KEY seteada).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


class ServicioIANoDisponibleError(Exception):
    """Falta la API key o falló la llamada a OpenAI (red, timeout, error de la API)."""


def cliente_openai():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ServicioIANoDisponibleError(
            "El asistente de IA no está configurado (falta OPENAI_API_KEY)."
        )
    from openai import OpenAI  # import diferido: no rompe el boot si falta la lib o la key

    return OpenAI(api_key=api_key)
