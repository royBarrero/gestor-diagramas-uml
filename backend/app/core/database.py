"""Configuración de la conexión a la base de datos PostgreSQL.

Expone el `engine`, la fábrica de sesiones `SessionLocal`, la clase `Base`
declarativa de la que heredan todos los modelos ORM, y la dependencia
`get_db` para usar en los endpoints de FastAPI más adelante.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Cargar el .env ubicado en la carpeta backend/ (dos niveles arriba de este archivo)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "Falta la variable DATABASE_URL. Definila en backend/.env "
        "(ejemplo: postgresql://usuario:password@localhost:5432/gestor_diagramas_db)."
    )

# pool_pre_ping evita errores por conexiones que el servidor cerró por inactividad
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependencia de FastAPI: entrega una sesión y la cierra al terminar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
