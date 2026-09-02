# Frontend — Allianz CICOS Claims Intelligence

SPA estática (Vite + React 19 + TS estricto) que consume el backend FastAPI
documentado en `docs/api/openapi.json`.

## Stack

| Capa | Tecnología |
|---|---|
| Build | Vite 6 |
| UI | React 19 + TypeScript (strict) |
| Estilos | Tailwind v3.4 + tokens CSS (claro/oscuro) |
| Componentes | Radix UI primitives + patrón shadcn/ui (cva + tailwind-merge) |
| Estado servidor | TanStack Query v5 |
| HTTP | openapi-fetch tipado contra `src/types/api.gen.ts` |
| Streaming | `fetch` + `ReadableStream` + `eventsource-parser@1` |
| Visor PDF | pdfjs-dist 4.10 con worker local |
| Tests unit | Vitest + Testing Library |
| Tests e2e | Playwright (Chrome estable del sistema) |
| Package mgr | pnpm 9 (workspace raíz) |

## Decisiones arquitectónicas (resumen)

| ID | Decisión |
|---|---|
| D1 | Mismo origin: el reverse proxy sirve SPA + `/api/v1/*`. `VITE_API_BASE_URL=""`. |
| D2 | Streaming SSE con `fetch` + `ReadableStream` + `eventsource-parser@1` (no `EventSource`). |
| D3 | `EnvelopeRenderer` usa `switch` literal sobre `result.kind` con `default: satisfies never`. |
| D4 | Si `evidence.regions` está vacío → overlay `#00378133` página completa + `console.warn`. |
| D5 | Tailwind v3.4 + tokens CSS (degradación documentada — ver commit body). |
| D6 | Tipos OpenAPI regenerados vía `predev`/`prebuild`/`pretest` (no `postinstall`). |

Ver `src/lib/storage.ts`, `src/features/queries/use-query-stream.ts`,
`src/components/envelope-renderer.tsx`, `src/components/pdf-viewer.tsx` y
`scripts/generate-openapi-types.mjs` para los detalles.

## Estructura

```
frontend/
├── scripts/generate-openapi-types.mjs   # Node puro
├── src/
│   ├── main.tsx                          # entry
│   ├── App.tsx                           # providers
│   ├── env.ts                            # validación zod de import.meta.env
│   ├── routes/_index.tsx                 # única ruta MVP
│   ├── components/                       # UI feature + primitivos shadcn/ui
│   ├── features/
│   │   ├── queries/                      # use-query + use-query-stream
│   │   ├── evidence/                     # EvidenceContext
│   │   └── pdf-viewer/                   # pdf-utils (pure functions)
│   ├── api/                              # client + health + types re-exports
│   ├── lib/                              # cn, request-id, storage, backoff
│   ├── styles/                           # tokens.css + globals.css
│   └── types/api.gen.ts                  # gitignored, regenerado
└── tests/
    ├── unit/                             # Vitest
    └── e2e/                              # Playwright
```

## Comandos (desde la raíz del monorepo)

```bash
# Instalar todo (raíz + workspace)
pnpm install

# Regenerar tipos manualmente
pnpm openapi:gen

# Verificar que no hay drift (lo usaremos en CI)
pnpm openapi:check

# Servidor de desarrollo
pnpm dev   # http://127.0.0.1:5173

# Build de producción
pnpm build

# Verificación
pnpm typecheck
pnpm lint
pnpm test        # vitest run
pnpm e2e         # arranca dev server + playwright
```

## Tipos OpenAPI — generación automática

Los tipos viven en `src/types/api.gen.ts` y **NO se commitean** (gitignored).

Se regeneran automáticamente antes de `dev`, `build` y `test` mediante los
hooks `predev`, `prebuild` y `pretest`. Razón: pnpm NO ejecuta `postinstall`
con `--frozen-lockfile`, así que no podemos depender de él para mantener los
tipos frescos en CI.

Para regenerar a mano:

```bash
pnpm openapi:gen       # regenera src/types/api.gen.ts
pnpm openapi:check     # regenera y falla si hay diff
```

El path al `openapi.json` se puede sobreescribir con la env var
`OPENAPI_JSON_PATH` (default: `../../docs/api/openapi.json` relativa a
`frontend/`).

## Variables de entorno

| Variable | Default | Descripción |
|---|---|---|
| `VITE_API_BASE_URL` | `""` | URL base del backend. Vacío = mismo origin. |
| `MODE` | `development` | Establecido por Vite. |
| `DEV` / `PROD` | según `vite` | Establecido por Vite. |

Sin secretos en el bundle. La auth la gestiona el reverse proxy.
