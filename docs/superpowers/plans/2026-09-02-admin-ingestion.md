# Modo administrador e ingesta por API — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reemplazar la operación de ingesta de la demo por un flujo API asíncrono y visible en la interfaz, restringido al manual CIDE/ASCIDE/CICOS verificado.

**Architecture:** Un servicio de jobs persistirá una única ejecución activa y sus eventos en un fichero JSON atómico bajo el directorio de datos de la aplicación. FastAPI iniciará el worker en background y expondrá snapshot, inicio, SSE y extracciones; el worker reutilizará directamente los casos de uso de extracción e indexación existentes, sin invocar procesos CLI. React añadirá el modo administrador desde el control superior derecho y volverá al chat sin perder hilos.

**Tech Stack:** Python 3.14, FastAPI, Pydantic, asyncio, SSE existente, React 19, TypeScript, Vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-09-02-admin-ingestion-design.md`

## Global Constraints

- Sólo se procesa `data/raw/Manual-cide-ascide-y-cicos.pdf` con SHA-256 `b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344`.
- No aceptar uploads, rutas, parsers o documentos aportados por el cliente.
- No llamar al CLI desde la API; reutilizar casos de uso y adaptadores Python.
- Mantener el índice activo durante la ejecución y sustituirlo sólo tras publicación atómica satisfactoria.
- No exponer secretos, rutas internas, stack traces ni el manual como derecho vigente.
- Un único job `running`; un segundo inicio devuelve HTTP 409.
- Cambios de comportamiento: prueba fallida antes del código de producción y gates antes de declarar completitud.

---

### Task 1: Modelo persistido y servicio de ejecución

**Files:**
- Create: `backend/src/application/models/ingestion.py`
- Create: `backend/src/application/services/ingestion_jobs.py`
- Test: `backend/tests/test_ingestion_jobs.py`

**Interfaces:**
- `IngestionJobStore.load() -> IngestionSnapshot`
- `IngestionJobStore.start() -> IngestionJob` (lanza `IngestionAlreadyRunning`)
- `IngestionJobStore.update(job_id, patch) -> IngestionJob`
- `IngestionJobStore.append_event(job_id, event) -> IngestionEvent`
- `IngestionJobService.start() -> IngestionJob`
- `IngestionJobService.snapshot() -> IngestionSnapshot`

- [x] **Steps 1–5.** Tests RED observados, store JSON atómico implementado y `2 passed` en la suite focalizada.

### Task 2: Worker que reutiliza la ingesta e indexación existentes

**Files:**
- Create: `backend/src/application/services/ingestion_runner.py`
- Modify: `backend/src/bootstrap.py`
- Test: `backend/tests/test_ingestion_runner.py`

**Interfaces:**
- `IngestionRunner.run(job_id: str) -> None`
- Dependency callables for manual verification/extraction and index publication, injected in tests and composed in `bootstrap.py`.

- [x] **Steps 1–5.** Runner probado con orden de fases, hash, error seguro y composición local sin subprocess CLI.

### Task 3: Endpoints FastAPI de administración

**Files:**
- Create: `backend/src/infrastructure/adapters/inbound/api/routes/admin_ingestion.py`
- Modify: `backend/src/infrastructure/adapters/inbound/api/app.py`
- Create: `backend/tests/test_admin_ingestion_api.py`

**Interfaces:**
- `GET /api/v1/admin/ingestion`
- `POST /api/v1/admin/ingestion`
- `GET /api/v1/admin/ingestion/events`
- `GET /api/v1/admin/ingestion/extractions?offset=0&limit=50`

- [x] **Steps 1–5.** Endpoints, SSE, paginación y OpenAPI implementados; `3 passed` focalizados y `make check-openapi` OK.

### Task 4: Cliente API y modo administrador en React

**Files:**
- Create: `frontend/src/api/ingestion.ts`
- Create: `frontend/src/components/admin/ingestion-panel.tsx`
- Modify: `frontend/src/routes/_index.tsx`
- Create: `frontend/tests/unit/admin-ingestion.test.tsx`

**Interfaces:**
- `getIngestionSnapshot(): Promise<IngestionSnapshot>`
- `startIngestion(): Promise<IngestionJob>`
- `subscribeToIngestion(onEvent, onError): () => void`

- [x] **Steps 1–5.** Panel, cliente API, SSE y lista de extracciones implementados; 92 tests, typecheck y build OK.

### Task 5: Integración real, documentación y verificación visual

**Files:**
- Modify: `docs/ESTADO.md`
- Modify: `README.md`
- Modify: `docs/superpowers/plans/2026-09-02-cierre-verificado.md`
- Test: `backend/tests/test_admin_ingestion_api.py`, `frontend/tests/unit/admin-ingestion.test.tsx`, `make test-e2e`

- [x] **Steps 1–2.** Stack normal `desktop-linux`; reingesta real iniciada desde UI, cuatro etapas, 111 páginas, 118 fragmentos y readiness `ready`.
- [x] **Step 3.** Verificación visual del panel y detalle de páginas en navegador local.
- [x] **Step 4.** Lint/Pyright/OpenAPI/frontend/e2e/doctor OK; `pnpm` wrapper bloqueado únicamente en comandos que intentan resolver `electron-to-chromium` demasiado reciente, por lo que se usaron binarios ya instalados para tests/build.
- [x] **Step 5.** `docs/ESTADO.md` actualizado como índice único.
