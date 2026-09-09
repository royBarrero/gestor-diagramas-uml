# Proyecto: Gestor de Diagramas UML (Clases)

## Descripción general

Software web colaborativo para diagramación de clases UML 2.5, inspirado en Enterprise Architect pero enfocado únicamente en diagramas de clases. Incluye capacidades de IA (voz, visión por computadora, agente conversacional) y generación automática de código (backend y frontend) a partir del diagrama diseñado por el usuario.

Este proyecto es el trabajo práctico individual de la materia Ingeniería de Software I (INF422), desarrollado bajo la metodología PUDS (Proceso Unificado de Desarrollo de Software / RUP), organizado en 2 ciclos iterativos.

## Stack tecnológico

- **Frontend web**: React + Vite + React Flow (`@xyflow/react`) para el lienzo de diagramación tipo nodos/conexiones. Axios para peticiones HTTP. Socket.io-client para tiempo real.
- **Backend**: FastAPI (Python), elegido porque facilita integrar librerías de IA (voz, visión, agente) sin necesidad de microservicios separados, y soporta WebSockets nativo para colaboración en tiempo real.
- **Base de datos**: PostgreSQL, con soporte JSON para guardar la estructura del diagrama.
- **Móvil / modo offline**: Flutter (fase futura, no se implementa todavía).

## Estructura del repositorio (monorepo)

```
gestor-diagramas-uml/
├── backend/      → FastAPI (entorno virtual en backend/venv, ya configurado)
├── frontend/     → React + Vite + React Flow (ya configurado)
├── mobile/       → Flutter (vacío por ahora, fase futura)
├── docs/         → Documentación del parcial (perfil, casos de uso, diagramas UML del propio proceso PUDS)
└── CLAUDE.md     → este archivo
```

### Backend — dependencias ya instaladas

fastapi, uvicorn[standard], sqlalchemy, psycopg2-binary, python-dotenv, pydantic, pydantic-settings, python-jose[cryptography], passlib[bcrypt], python-multipart.

El archivo `.env` en `backend/` ya contiene `DATABASE_URL`, `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `ENVIRONMENT`. La base de datos PostgreSQL ya está creada y accesible.

### Frontend — dependencias ya instaladas

react, react-dom, @xyflow/react, axios, socket.io-client (además de lo que trae el template de Vite con ESLint).

## Actores del sistema

- **Usuario** (actor base, abstracto): agrupa casos de uso compartidos — login, registro, cerrar sesión, diagramar, colaborar.
- **Administrador**: dueño/creador de un proyecto. Gestiona el proyecto, sus miembros, y genera backend/frontend a partir del diagrama.
- **Colaborador**: usuario invitado a un proyecto. Puede diagramar y colaborar en tiempo real, pero no gestiona miembros ni genera código.

Los módulos de IA (voz, foto, agente) NO son actores — son funcionalidad interna del sistema, no interactúan como actor externo en los diagramas de casos de uso.

## Alcance funcional completo (14 casos de uso)

### Ciclo 1 — Core + colaboración (prioridad alta, base indispensable del sistema)

- **CU01. Gestionar Inicio de Sesión**
- **CU02. Gestionar Registro de Usuario**
- **CU03. Gestionar Cierre de Sesión** (incluye CU01)
- **CU04. Gestionar Proyectos** (incluye CU01)
- **CU05. Gestionar Miembros del Proyecto** (incluye CU04, solo Administrador)
- **CU06. Gestionar Diagrama de Clases** (incluye CU04) — crear/editar/eliminar clases, atributos, métodos, relaciones (herencia, asociación, agregación, composición, dependencia)
- **CU07. Gestionar Colaboración en Tiempo Real** (incluye CU06) — vía WebSockets, edición simultánea sobre el mismo diagrama

### Ciclo 2 — IA + interoperabilidad + generación de código (según avance)

- **CU08. Gestionar Creación de Clases por Comando de Voz**
- **CU09. Gestionar Digitalización de Diagrama por Fotografía** (visión por computadora)
- **CU10. Gestionar Exportación e Importación de Diagramas** (JSON, imagen, XMI compatible con Enterprise Architect)
- **CU11. Gestionar Generación de Backend** (Spring Boot con JPA/Hibernate, CRUD, endpoints REST, a partir del diagrama)
- **CU12. Gestionar Generación de Frontend** (Flutter, a partir del backend generado)
- **CU13. Gestionar Agente Asistente** (chat conversacional integrado — prioridad baja / stretch)
- **CU14. Gestionar Modo Offline** (IA local en Flutter — prioridad baja / stretch, el más riesgoso técnicamente)

Nota de priorización: dentro del Ciclo 2, el orden de avance preferido es voz → foto → generación de backend, antes que frontend/agente/offline. Agente Asistente y Modo Offline son los que más probablemente queden solo documentados sin implementación completa.

## Modelo de base de datos (entidades y atributos)

### Usuario
- id (PK)
- nombre
- email (único)
- password_hash
- created_at

### Proyecto
- id (PK)
- nombre
- descripcion
- id_usuario_creador (FK → Usuario)
- created_at

### MiembroProyecto
Tabla intermedia que resuelve la relación muchos a muchos entre Usuario y Proyecto, y guarda el rol de cada usuario dentro de ese proyecto.
- id (PK)
- id_proyecto (FK → Proyecto)
- id_usuario (FK → Usuario)
- rol (administrador / colaborador)
- fecha_union

### Diagrama
- id (PK)
- id_proyecto (FK → Proyecto)
- nombre
- contenido (JSONB — acá van los nodos/clases, atributos, métodos y relaciones del diagrama, tal como los maneja React Flow)
- updated_at

## Estilo de trabajo esperado de Claude Code

- Conversación tipo compañero de trabajo desarrollando el proyecto en conjunto, sin encuestas de opción múltiple ni checklists innecesarios.
- **No adelantar contenido, código, ni archivos que no fueron pedidos explícitamente.** Si algo parece un siguiente paso lógico, se sugiere primero y se espera confirmación antes de implementarlo.
- Se trabaja de a un caso de uso (o una funcionalidad puntual) por vez, avanzando de forma incremental y ordenada.
- Al escribir o modificar código, indicar siempre con claridad en qué carpeta y archivo se está trabajando.
- Priorizar que el Ciclo 1 (CU01–CU07) quede completamente sólido y funcional antes de avanzar en profundidad con el Ciclo 2.
- Mantener buenas prácticas de organización típicas de FastAPI (separación en routers, models, schemas, services/crud, core/config) y de React (componentes, hooks, servicios de API) a medida que el proyecto crece — pero sin sobre-diseñar de entrada cosas que no se han pedido.

## Convenciones de Git

- Rama principal: `main`.
- El repositorio ya tiene `.gitignore` configurado correctamente para excluir `backend/venv/`, `backend/.env`, `frontend/node_modules/`, y carpetas de build/caché en general.
- Se realizan commits descriptivos por avance funcional (por ejemplo, por caso de uso completado), no commits gigantes que mezclen features distintas.