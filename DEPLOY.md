# Despliegue

Este documento describe los pasos para desplegar el proyecto usando Docker. La preparación (Dockerfiles, docker-compose, configuraciones) ya está lista en el repo; lo que sigue son los pasos manuales que quedan a cargo de quien despliega (creación de la instancia, DNS, HTTPS, etc.).

## 1. Prerrequisitos en el servidor/VPS

- Docker Engine y el plugin Docker Compose instalados (`docker compose version` debe funcionar).
- Puertos abiertos según corresponda (por ejemplo 80/443 si vas a poner un reverse proxy delante, o 8000/5173 si vas a exponerlos directo).

## 2. Configurar variables de entorno

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env   # opcional, solo referencia para dev local
```

Completar en `backend/.env`:
- `DATABASE_URL`: si usás el Postgres del `docker-compose.yml`, el host es `db` (no `localhost`). Si usás un Postgres administrado externo, apuntá al host/puerto/credenciales reales.
- `SECRET_KEY`: una clave larga y aleatoria, distinta de cualquier valor de desarrollo.
- `CORS_ORIGINS`: el dominio o IP pública real donde vas a servir el frontend (ej. `https://tu-dominio.com`). Sin esto, el navegador va a bloquear las requests al backend.
- `OPENAI_API_KEY`: opcional; sin ella, CU08 (voz) y CU09 (foto) devuelven un error controlado en vez de romper el arranque del backend.

Para el frontend, la URL del backend (`VITE_API_URL`) **no se lee en runtime**: Vite la resuelve en build-time. Definila al buildear:

```bash
VITE_API_URL=https://tu-dominio-o-ip-del-backend docker compose build frontend
```

(si no la definís, cae por defecto a `http://localhost:8000`, que solo sirve para pruebas en tu propia máquina).

## 3. Levantar el stack

```bash
docker compose up -d --build
docker compose ps   # confirmar que db, backend y frontend están "healthy"/"running"
```

## 4. Crear las tablas (una sola vez)

No hay migraciones (no se usa Alembic); `create_tables.py` hace `create_all`, que es seguro correr una sola vez después del primer `up` y no dropea/recrea tablas existentes:

```bash
docker compose exec backend python create_tables.py
```

Si más adelante cambiás los modelos, vas a necesitar una estrategia de migraciones (Alembic) — eso queda fuera de este preparado.

## 5. Smoke test

1. Abrir el frontend (puerto 5173, o el dominio que hayas configurado).
2. Registrar un usuario, loguear.
3. Crear un proyecto, abrir la pizarra de diagramas.
4. Confirmar que el indicador de colaboradores queda "conectado" (no se traba en "conectando") — valida que CORS y Socket.IO están bien configurados.
5. Probar un endpoint de generación de código (CU11/CU12) y confirmar que descarga el zip correctamente.

## 6. Lo que queda fuera de este preparado (a resolver manualmente)

- **HTTPS/certificados**: no hay reverse proxy ni Let's Encrypt/Certbot configurado. Si exponés el servicio públicamente, poné algo delante (nginx/Caddy/Traefik) que termine TLS.
- **Dominio**: configurar el DNS apuntando a la IP del VPS.
- **Backups de Postgres**: el volumen `pgdata` persiste datos entre reinicios del contenedor, pero no hay ningún backup automático configurado.
- **Escalado horizontal del backend**: el backend corre con un solo worker de uvicorn a propósito, porque el estado de colaboradores en tiempo real (`app/realtime.py`) vive en memoria de un solo proceso. Escalar a más de una réplica requeriría mover ese estado a algo compartido (ej. Redis con el adapter de python-socketio) — no implementado.
- **Rotación de `SECRET_KEY`** y buenas prácticas de manejo de secretos en el servidor.
- **Firewall** del VPS (solo dejar abiertos los puertos que realmente necesitás expuestos).

## Troubleshooting rápido

- **El build del backend falla en `pip install`**: revisar el log completo del build; si es por resolución de paquetes, confirmar versión de Docker/BuildKit.
- **El frontend no puede hablar con el backend** (errores de red en la consola del navegador): la causa más común es `VITE_API_URL` mal seteado al buildear el frontend, o `CORS_ORIGINS` en `backend/.env` sin el dominio real desde el que se sirve el frontend.
- **El backend no arranca / no conecta a la base**: si usás el Postgres del compose, confirmar que `DATABASE_URL` usa el host `db`, no `localhost`.
