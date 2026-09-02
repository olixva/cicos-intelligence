# Repository Reorganization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aislar frontend y backend dentro de sus carpetas, limpiar artefactos locales y dejar `main` como única rama local y remota sin perder trabajo existente.

**Architecture:** El frontend se convierte en un paquete pnpm autónomo con manifest, lockfile y configuración propios. El backend conserva su proyecto uv y absorbe los scripts OpenAPI; la raíz queda limitada a coordinación, infraestructura, datos y documentación compartida.

**Tech Stack:** Git, pnpm 9.12, Node.js 20.18+, uv, Python 3.14, Docker Compose, Make.

**Spec:** `docs/superpowers/specs/2026-09-02-reorganizacion-repositorio-design.md`

## Global Constraints

- No usar `git reset --hard`, `git clean -fd` ni borrados recursivos sobre rutas amplias.
- No borrar `data/`, `.env`, `ops/local.env`, volúmenes o imágenes Docker.
- No eliminar la rama feature remota hasta verificar que `main` contiene todos sus commits.
- Clasificar cada fichero pendiente antes de conservarlo, ignorarlo o eliminarlo.
- Los movimientos y ediciones se hacen con `apply_patch`; las instalaciones y formatos mecánicos pueden usar sus comandos nativos.

---

### Task 1: Clasificar y preservar el estado pendiente

**Files:**
- Modify: `.gitignore`
- Preserve: `README.md`, `.dockerignore`, `backend/Dockerfile`, `frontend/Dockerfile`, `docs/audit/2026-09-02-auditoria-integral-specs.md`, `docs/superpowers/plans/2026-09-02-remediacion-ux-observabilidad.md`
- Review: `docs/screenshots/*.png`

**Interfaces:**
- Consumes: estado Git actual en `feat/rag-continuation-2026-09`.
- Produces: árbol sin artefactos IDE/Playwright visibles y lista cerrada de entregables que deben llegar a `main`.

- [ ] **Step 1: Capturar inventario exacto**

Run: `git status --short --branch && git ls-files --others --exclude-standard`

Expected: aparecen cambios útiles y artefactos locales por separado; no se modifica el árbol.

- [ ] **Step 2: Añadir ignores específicos**

Modificar `.gitignore` para incluir exactamente:

```gitignore
.idea/
.playwright-mcp/
**/node_modules/
frontend/playwright-report/
frontend/test-results/
frontend/*.tsbuildinfo
```

- [ ] **Step 3: Eliminar solo artefactos regenerables identificados**

Eliminar mediante parches o comandos de borrado con rutas literales verificadas: `.idea/`, `.playwright-mcp/`, `node_modules/`, `frontend/dist/`, `frontend/playwright-report/`, `frontend/test-results/` y `frontend/*.tsbuildinfo`. Mantener `frontend/node_modules/` hasta regenerar el lockfile.

- [ ] **Step 4: Verificar clasificación**

Run: `git status --short && git check-ignore -v .idea/workspace.xml .playwright-mcp/example.log node_modules/example frontend/test-results/example`

Expected: ningún artefacto local aparece como candidato a commit; los entregables útiles siguen presentes.

### Task 2: Convertir frontend en paquete pnpm autónomo

**Files:**
- Delete: `package.json`
- Delete: `pnpm-workspace.yaml`
- Move: `pnpm-lock.yaml` → `frontend/pnpm-lock.yaml`
- Move: `.npmrc` → `frontend/.npmrc`
- Modify: `frontend/Dockerfile`
- Modify: `Makefile`
- Modify: `README.md`

**Interfaces:**
- Consumes: `frontend/package.json` y dependencias bloqueadas actuales.
- Produces: comandos `pnpm --dir frontend ...` e imagen frontend sin dependencia del workspace raíz.

- [ ] **Step 1: Mover configuración y retirar workspace**

Aplicar movimientos de `.npmrc` y lockfile; eliminar el manifest coordinador y `pnpm-workspace.yaml`.

- [ ] **Step 2: Regenerar el lockfile desde frontend**

Run: `pnpm --dir frontend install --lockfile-only`

Expected: `frontend/pnpm-lock.yaml` referencia `lockfileVersion` y un importer `.`; no crea manifests en raíz.

- [ ] **Step 3: Actualizar Dockerfile frontend**

El build debe usar contexto `frontend/` y estas copias relativas:

```dockerfile
COPY package.json pnpm-lock.yaml .npmrc ./
RUN pnpm install --frozen-lockfile
COPY . .
RUN pnpm build
```

La generación OpenAPI debe recibir el snapshot mediante un stage/context explícito o ejecutarse antes del build; no debe leer un workspace pnpm raíz inexistente.

- [ ] **Step 4: Actualizar comandos coordinadores**

Makefile y README deben usar:

```bash
pnpm --dir frontend dev
pnpm --dir frontend build
pnpm --dir frontend test
pnpm --dir frontend e2e
docker build -t allianz-frontend frontend
```

- [ ] **Step 5: Verificar frontend aislado**

Run: `pnpm --dir frontend install --frozen-lockfile && pnpm --dir frontend lint && pnpm --dir frontend typecheck && pnpm --dir frontend test && pnpm --dir frontend build`

Expected: todos los comandos terminan con exit 0; `find . -maxdepth 1 -name 'package.json' -o -name 'pnpm-lock.yaml' -o -name 'pnpm-workspace.yaml' -o -name '.npmrc'` no devuelve resultados.

### Task 3: Mover tooling exclusivo del backend

**Files:**
- Move: `scripts/export_openapi.py` → `backend/scripts/export_openapi.py`
- Move: `scripts/check_openapi.py` → `backend/scripts/check_openapi.py`
- Modify: ambos scripts
- Modify: `Makefile`
- Modify: `README.md`
- Modify: referencias operativas en `docs/superpowers/plans/2026-08-31-allianz-rag-implementation.md`

**Interfaces:**
- Consumes: factory `bootstrap:build_api` y snapshot `docs/api/openapi.json`.
- Produces: `uv run --project backend python backend/scripts/{export,check}_openapi.py`.

- [ ] **Step 1: Mover los scripts conservando historial**

Crear los dos ficheros bajo `backend/scripts/` con el contenido actual y eliminar sus equivalentes raíz.

- [ ] **Step 2: Hacer robusta la resolución de raíz**

En ambos scripts, calcular:

```python
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
OPENAPI_PATH = REPOSITORY_ROOT / "docs" / "api" / "openapi.json"
```

y ajustar imports/rutas a partir de `REPOSITORY_ROOT`.

- [ ] **Step 3: Actualizar invocaciones**

Sustituir referencias operativas por:

```bash
uv run --project backend python backend/scripts/export_openapi.py
uv run --project backend python backend/scripts/check_openapi.py
```

- [ ] **Step 4: Verificar contrato**

Run: `uv run --project backend python backend/scripts/check_openapi.py && pnpm --dir frontend openapi:check`

Expected: `openapi.json is up to date` y tipos frontend sin diferencias.

### Task 4: Verificar estructura y crear el commit de reorganización

**Files:**
- Modify: `.dockerignore`
- Modify: documentación que conserve referencias antiguas operativas
- Commit: todos los entregables clasificados de Tasks 1–3

**Interfaces:**
- Consumes: frontend/backend ya aislados.
- Produces: commit verificable que puede avanzar `main`.

- [ ] **Step 1: Simplificar ignores de build**

Mantener reglas explícitas para `.git/`, `.slim/`, `.idea/`, `.playwright-mcp/`, `.worktrees/`, `**/node_modules/`, `backend/.venv/`, caches, resultados de test, `.env*` salvo ejemplos, `data/` y `ops/local.env`.

- [ ] **Step 2: Buscar referencias obsoletas**

Run: `rg -n 'pnpm --filter|pnpm-workspace|scripts/(check|export)_openapi|docker build .*frontend/Dockerfile' README.md Makefile backend frontend docs`

Expected: cero referencias operativas obsoletas; las menciones históricas en specs se etiquetan como históricas o se actualizan si son instrucciones ejecutables.

- [ ] **Step 3: Ejecutar gates backend y coordinación**

Run: `make check-backend && uv run --project backend python backend/scripts/check_openapi.py && docker --context colima-allianz compose --env-file ops/local.env config --quiet`

Expected: checks y Compose pasan; si Docker build falla solo por falta de espacio, registrar el bloqueo sin borrar volúmenes.

- [ ] **Step 4: Revisar diff y secretos**

Run: `git diff --check && git status --short && git diff --stat && git diff --cached --check`

Expected: ningún whitespace error, credencial, `.env` real, dependencia instalada o artefacto local preparado para commit.

- [ ] **Step 5: Commit de reorganización**

```bash
git add .gitignore .dockerignore Makefile README.md backend frontend docs pnpm-lock.yaml package.json pnpm-workspace.yaml .npmrc scripts
git commit -m "chore: reorganize repository boundaries"
```

Usar pathspecs existentes y eliminados de forma segura; no añadir `data/`, `.env` ni artefactos ignorados.

### Task 5: Integrar en main y dejar una sola rama

**Files:**
- Git refs: `main`, `origin/main`, `feat/rag-continuation-2026-09`, `origin/feat/rag-continuation-2026-09`

**Interfaces:**
- Consumes: rama feature limpia y verificada.
- Produces: `main` local/remota en el mismo commit; única rama del proyecto.

- [ ] **Step 1: Comprobar precondiciones**

Run: `git status --porcelain && git merge-base --is-ancestor main HEAD && git rev-list --left-right --count main...HEAD`

Expected: status vacío, ancestor exit 0 y `main` sin commits exclusivos.

- [ ] **Step 2: Publicar la feature verificada como seguridad**

Run: `git push origin feat/rag-continuation-2026-09`

Expected: origin contiene el commit final antes de modificar refs.

- [ ] **Step 3: Avanzar main sin merge commit**

Run: `git switch main && git merge --ff-only feat/rag-continuation-2026-09 && git push origin main`

Expected: `main`, `origin/main` y feature apuntan al mismo commit.

- [ ] **Step 4: Eliminar ramas feature**

Run: `git branch -d feat/rag-continuation-2026-09 && git push origin --delete feat/rag-continuation-2026-09 && git fetch --prune`

Expected: solo `main` y `origin/main` aparecen en `git branch -a`.

- [ ] **Step 5: Verificación final**

Run: `git status --short --branch && git branch -a && git worktree list && find . -maxdepth 1 \( -name package.json -o -name pnpm-lock.yaml -o -name pnpm-workspace.yaml -o -name .npmrc -o -name node_modules \) -print`

Expected: `## main...origin/main`, un único worktree, una única rama y ninguna dependencia/configuración frontend en raíz.
