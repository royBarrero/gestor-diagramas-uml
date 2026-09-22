FROM python:3.14-slim

WORKDIR /app

# Copiar primero requirements.txt para aprovechar el cache de capas de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m appuser
USER appuser

EXPOSE 8000

# Un solo worker: el roster de colaboradores en tiempo real (app/realtime.py)
# se guarda en memoria del proceso, no en Redis ni en la base de datos.
# Correr con --workers > 1 (o varias réplicas del contenedor) rompería CU07.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
