"""Script para crear las tablas en PostgreSQL a partir de los modelos ORM.

Uso: python create_tables.py (desde backend/, con el venv activado)
"""

from app.core.database import Base, engine
import app.models  # noqa: F401  (registra Usuario, Proyecto, MiembroProyecto, Diagrama en Base.metadata)

Base.metadata.create_all(bind=engine)

print("Tablas creadas correctamente:")
for table in Base.metadata.sorted_tables:
    print(f"  - {table.name}")
