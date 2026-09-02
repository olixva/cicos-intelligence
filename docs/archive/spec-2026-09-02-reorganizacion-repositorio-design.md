> [!WARNING]
> **DOCUMENTO ARCHIVADO — NO SEGUIR.** Archivado el 2026-09-02.
> Diseño de la reorganización, completada en `ce2d942`.
>
> Fuente de verdad actual: [`docs/ESTADO.md`](../ESTADO.md).
> Plan vigente: [`docs/superpowers/plans/2026-09-02-cierre-entrega-final.md`](../superpowers/plans/2026-09-02-cierre-entrega-final.md).

# Diseño — Reorganización del repositorio Allianz RAG

## Objetivo

Convertir el repositorio actual en un proyecto con frontend y backend autocontenidos, manteniendo en la raíz únicamente coordinación, documentación, datos y operación compartida. Integrar la rama de trabajo actual en `main` y dejar `main` como única rama local y remota del proyecto.

## Estructura objetivo

```text
/
├── backend/
│   ├── Dockerfile
│   ├── scripts/
│   ├── src/
│   ├── tests/
│   ├── pyproject.toml
│   └── uv.lock
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── pnpm-lock.yaml
│   ├── .npmrc
│   ├── src/
│   └── tests/
├── data/
├── docs/
├── ops/
├── .env.example
├── .gitignore
├── .dockerignore
├── compose.yaml
├── Makefile
└── README.md
```

## Decisiones

### Git

- La rama `feat/rag-continuation-2026-09` está 22 commits por delante de `main` y `main` es ancestro directo, por lo que la integración debe ser fast-forward, sin merge commit.
- Antes de cambiar de rama se preservarán y clasificarán todos los cambios pendientes.
- Los cambios útiles se incorporarán mediante un commit explícito; los artefactos generados se ignorarán o eliminarán.
- Tras verificar `main`, se eliminarán las ramas feature local y remota. No se reescribirá historia ni se usará `reset --hard`.

### Frontend

- El repositorio dejará de ser un workspace pnpm: solo existe un paquete JavaScript y el workspace raíz no aporta aislamiento útil.
- `package.json` raíz y `pnpm-workspace.yaml` desaparecerán.
- `pnpm-lock.yaml` y `.npmrc` pertenecerán a `frontend/`.
- La instalación y todos los comandos pnpm se ejecutarán desde `frontend/` o mediante `pnpm --dir frontend` desde el Makefile.
- El `node_modules/` raíz es un artefacto local y se eliminará; `frontend/node_modules/` seguirá ignorado y se regenerará desde su lockfile.

### Backend

- Los scripts que importan el backend y producen/verifican su contrato OpenAPI pasarán de `scripts/` a `backend/scripts/`.
- Sus rutas de entrada/salida seguirán apuntando al snapshot compartido `docs/api/openapi.json`.
- Python, configuración, Dockerfile, lockfile y tests permanecen dentro de `backend/`.

### Raíz compartida

- `Makefile`, `compose.yaml`, `README.md`, `.env.example`, `.gitignore` y `.dockerignore` permanecen en raíz por coordinar ambos componentes.
- `ops/` permanece en raíz porque contiene infraestructura compartida y configuración local de Langfuse/Qdrant.
- `docs/` y `data/` permanecen en raíz por ser artefactos transversales.
- La raíz no contendrá dependencias instaladas, manifests específicos de frontend ni scripts exclusivos de backend.

### Artefactos locales

- Se eliminarán `.idea/`, `.playwright-mcp/`, `node_modules/` raíz, cachés, `dist/`, `test-results/` y `playwright-report/` cuando no estén versionados.
- Se conservarán las capturas ya versionadas y solo se incorporarán capturas nuevas cuando estén referenciadas por documentación útil.
- No se borrarán `data/`, volúmenes Docker, `.env`, credenciales ni publicaciones de ingestión.

## Cambios de integración

- Actualizar `frontend/Dockerfile` para instalar desde el contexto y lockfile de `frontend/`, sin depender del workspace raíz.
- Actualizar Makefile y README para ejecutar pnpm en `frontend/`.
- Actualizar scripts, comentarios y documentación que mencionen las rutas antiguas.
- Ajustar `.gitignore` y `.dockerignore` a la nueva estructura, evitando reglas duplicadas o demasiado amplias.
- Mantener la generación de tipos OpenAPI reproducible desde frontend y la exportación/check desde backend.

## Manejo de errores y recuperación

- Antes de cada eliminación se comprobará que el objetivo es un artefacto no versionado y regenerable.
- Los movimientos versionados se harán de forma que Git pueda detectar renames.
- Si una verificación falla después de mover archivos, se corregirán rutas sobre la misma rama; no se descartarán cambios previos del usuario.
- La rama feature remota no se eliminará hasta que `main` contenga los commits y todos los gates posibles hayan pasado.

## Verificación

1. `git status` no muestra artefactos locales ni cambios sin clasificar.
2. Solo existe `main` localmente y en `origin`, además de `origin/HEAD`.
3. No existen `package.json`, `pnpm-lock.yaml`, `pnpm-workspace.yaml`, `.npmrc` ni `node_modules` en raíz.
4. `pnpm install --frozen-lockfile`, lint, typecheck, unit tests y build funcionan desde `frontend/`.
5. Backend lint, format check, pyright y pytest funcionan desde raíz mediante Makefile.
6. La exportación y comprobación OpenAPI funcionan desde `backend/scripts/`; los tipos frontend se regeneran sin diferencias.
7. `docker compose config` valida y ambos Dockerfiles alcanzan al menos la fase de parse/build; si Colima sigue sin espacio, se registra como bloqueo externo sin borrar volúmenes.
8. Una búsqueda global no encuentra referencias operativas a las rutas retiradas.

## Fuera de alcance

- No se corrigen en esta reorganización los defectos funcionales y visuales inventariados en la auditoría.
- No se modifica el contenido de datasets, publicaciones, Qdrant o Langfuse.
- No se introduce un nuevo gestor de monorepo, CI o sistema de despliegue.
