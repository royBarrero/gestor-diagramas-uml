# Despliegue

Este documento describe los pasos para desplegar el proyecto usando Docker. La preparación (Dockerfiles, docker-compose, configuraciones) ya está lista en el repo; lo que sigue son los pasos manuales que quedan a cargo de quien despliega (creación de la instancia, DNS, HTTPS, etc.).

## 1. Prerrequisitos en el servidor/VPS

- Docker Engine y el plugin Docker Compose instalados (`docker compose version` debe funcionar).
- Puertos 80 y 443 abiertos (los usa el servicio `proxy` para servir HTTPS — ver sección 2.1).

### 1.1 Por qué hace falta HTTPS (no es opcional)

El navegador bloquea el acceso al micrófono (`getUserMedia`, usado por CU08 — comando de voz) en cualquier página que no se sirva por HTTPS o `localhost`. Si exponés el sitio por `http://<IP>` sin más, CU08 va a fallar con un mensaje de "permisos" aunque el usuario nunca haya denegado nada — el contexto simplemente no es seguro. El stack ya trae un reverse proxy (`proxy`, con Caddy) que resuelve esto automáticamente.

## 2. Configurar variables de entorno

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env   # opcional, solo referencia para dev local
```

Completar en `backend/.env`:
- `DATABASE_URL`: si usás el Postgres del `docker-compose.yml`, el host es `db` (no `localhost`). Si usás un Postgres administrado externo, apuntá al host/puerto/credenciales reales.
- `SECRET_KEY`: una clave larga y aleatoria, distinta de cualquier valor de desarrollo.
- `CORS_ORIGINS`: el dominio HTTPS real donde vas a servir el frontend (ej. `https://app.203-0-113-5.sslip.io`, ver sección 2.1). Sin esto, el navegador va a bloquear las requests al backend.
- `OPENAI_API_KEY`: opcional; sin ella, CU08 (voz) y CU09 (foto) devuelven un error controlado en vez de romper el arranque del backend.

Para el frontend, la URL del backend (`VITE_API_URL`) **no se lee en runtime**: Vite la resuelve en build-time. Definila al buildear:

```bash
VITE_API_URL=https://api.203-0-113-5.sslip.io docker compose build frontend
```

(si no la definís, cae por defecto a `http://localhost:8000`, que solo sirve para pruebas en tu propia máquina).

## 2.1 HTTPS sin dominio propio (Caddy + sslip.io)

El repo trae un `Caddyfile` y un servicio `proxy` en `docker-compose.yml` que sirven el stack por HTTPS con certificado Let's Encrypt emitido y renovado automáticamente — no hace falta Certbot ni configuración manual de TLS.

Si no tenés un dominio propio, podés usar **sslip.io**: cualquier subdominio de `<algo>.<ip-con-guiones>.sslip.io` resuelve a esa IP sin que tengas que configurar DNS. Por ejemplo, si la IP pública del VPS es `203.0.113.5`:
- `app.203-0-113-5.sslip.io` → frontend
- `api.203-0-113-5.sslip.io` → backend

Pasos:
1. Editar `Caddyfile` en la raíz del repo y reemplazar `SUBDOMINIO` en ambos bloques por la IP del VPS con guiones (o por tu dominio real, si tenés uno — en ese caso usá directamente `tu-dominio.com` en vez del esquema `app.`/`api.`).
2. Usar esos mismos hosts en `CORS_ORIGINS` (backend) y `VITE_API_URL` (build del frontend), como se indica arriba.
3. Asegurarte de que los puertos 80 y 443 estén abiertos en el firewall del VPS — Caddy los necesita para el challenge HTTP-01 de Let's Encrypt y para servir HTTPS.

Si preferís no usar el proxy (por ejemplo, para pruebas rápidas sin HTTPS), el frontend y el backend siguen quedando accesibles directo en los puertos `5173` y `8000` — pero en ese caso CU08 (comando de voz) no va a funcionar, por la razón explicada en 1.1.

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

1. Abrir el frontend por HTTPS (`https://app.<ip-con-guiones>.sslip.io`, o el dominio que hayas configurado — ver 2.1).
2. Registrar un usuario, loguear.
3. Crear un proyecto, abrir la pizarra de diagramas.
4. Confirmar que el indicador de colaboradores queda "conectado" (no se traba en "conectando") — valida que CORS y Socket.IO están bien configurados.
5. Probar un endpoint de generación de código (CU11/CU12) y confirmar que descarga el zip correctamente.
6. Probar CU08 (comando de voz): el navegador debe pedir permiso de micrófono (prompt nativo), no mostrar directamente el error de "revisá los permisos".

## 6. Lo que queda fuera de este preparado (a resolver manualmente)

- **Dominio propio**: si no usás sslip.io, configurar el DNS apuntando a la IP del VPS.
- **Backups de Postgres**: el volumen `pgdata` persiste datos entre reinicios del contenedor, pero no hay ningún backup automático configurado.
- **Escalado horizontal del backend**: el backend corre con un solo worker de uvicorn a propósito, porque el estado de colaboradores en tiempo real (`app/realtime.py`) vive en memoria de un solo proceso. Escalar a más de una réplica requeriría mover ese estado a algo compartido (ej. Redis con el adapter de python-socketio) — no implementado.
- **Rotación de `SECRET_KEY`** y buenas prácticas de manejo de secretos en el servidor.
- **Firewall** del VPS (solo dejar abiertos los puertos que realmente necesitás expuestos).

## Troubleshooting rápido

- **El build del backend falla en `pip install`**: revisar el log completo del build; si es por resolución de paquetes, confirmar versión de Docker/BuildKit.
- **El frontend no puede hablar con el backend** (errores de red en la consola del navegador): la causa más común es `VITE_API_URL` mal seteado al buildear el frontend, o `CORS_ORIGINS` en `backend/.env` sin el dominio real desde el que se sirve el frontend.
- **El backend no arranca / no conecta a la base**: si usás el Postgres del compose, confirmar que `DATABASE_URL` usa el host `db`, no `localhost`.
- **CU08 (voz) falla con "revisá los permisos del navegador" sin que el navegador llegue a pedir permiso**: el sitio se está sirviendo por HTTP, no HTTPS. Ver sección 2.1 — `getUserMedia` no existe en contextos no seguros.
- **`proxy` no consigue el certificado Let's Encrypt** (ver `docker compose logs proxy`): confirmar que el `Caddyfile` tiene el host real (no quedó `SUBDOMINIO` sin reemplazar) y que los puertos 80/443 están efectivamente abiertos y llegan al VPS (firewall del proveedor + firewall del SO).
