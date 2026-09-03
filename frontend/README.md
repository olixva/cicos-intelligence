# Frontend

SPA estática (Vite + React 19 + TypeScript estricto) que consume el API
documentado en [`docs/api/openapi.json`](../docs/api/openapi.json).

Contexto general en el [README raíz](../README.md); arquitectura completa en
[docs/arquitectura.md](../docs/arquitectura.md).

## Stack

| Capa | Tecnología |
|---|---|
| Build | Vite 6 |
| UI | React 19 + TypeScript estricto |
| Estilos | Tailwind 3.4 + tokens CSS (claro / oscuro) |
| Componentes | primitivas de Radix UI con el patrón shadcn/ui (`cva` + `tailwind-merge`) |
| Estado servidor | TanStack Query v5 |
| HTTP | `openapi-fetch` tipado contra `src/types/api.gen.ts` |
| Streaming | `fetch` + `ReadableStream` + `eventsource-parser` |
| Visor PDF | `pdfjs-dist` 4.10 con worker local |
| Tests | Vitest + Testing Library · Playwright para e2e |
| Paquetes | pnpm 9 |

## Estructura

```
frontend/
├── scripts/generate-openapi-types.mjs   generación de tipos (Node puro)
├── src/
│   ├── main.tsx / App.tsx      entrada y providers
│   ├── env.ts                  validación zod de import.meta.env
│   ├── routes/_index.tsx       la única ruta: el chat completo
│   ├── api/                    cliente tipado, health, queries, ingesta
│   ├── components/
│   │   ├── thread/             mensajes, panel de siniestro, aclaraciones, markdown
│   │   ├── composer/           entrada con selector de modo
│   │   ├── tool-call/          tarjetas de etapa del workflow
│   │   ├── citation/           chips de cita
│   │   ├── pdf-overlay/        visor modal del PDF original
│   │   ├── sidebar/            historial de hilos
│   │   ├── admin/              panel de ingesta
│   │   └── ui/                 primitivas shadcn/ui
│   ├── lib/                    reducer del hilo, cliente SSE, almacenamiento,
│   │                           formato de resultados, utilidades de PDF
│   ├── styles/                 tokens.css + globals.css
│   └── types/api.gen.ts        generado, no versionado
└── tests/
    ├── unit/                   Vitest (18 ficheros, 98 tests)
    └── e2e/                    Playwright
```

## Cómo funciona

**El hilo es un reducer puro.** `lib/thread-state.ts` deriva sus acciones 1:1
de los eventos SSE del backend (`started | stage | completed | failed`) más las
acciones del usuario (`SUBMIT`, `CANCEL`, `OPEN_PDF`, `CLOSE_PDF`). El hook
`useThread`, en el mismo módulo, lo conecta al ciclo de vida real con `fetch` y
`AbortController`.

El transporte es propio en lugar de un runtime de chat de terceros: los
runtimes al uso asumen una forma de transporte distinta a la del SSE de este
backend, y acoplarse a ellos obligaría a adaptar el contrato del servidor. El
cliente vive en `lib/streaming-client.ts` sobre `eventsource-parser`.

**El backend es la única fuente de verdad de etapas y tiempos.** La interfaz no
fabrica duraciones: cuando el backend no emite un tiempo por etapa, la tarjeta
de *tool call* muestra «OK» en lugar de un número inventado.

**Las citas abren la fuente.** Un chip de cita abre el PDF original en la
página exacta. El visor carga `pdfjs-dist` de forma perezosa y **rasteriza sólo
la página que se está mirando**: rasterizar las 111 páginas antes de mostrar la
primera dejaba la primera cita esperando durante minutos. Si la evidencia no
trae regiones, el resaltado cae a página completa con un aviso por consola en
lugar de no mostrar nada.

**El historial es real.** `lib/thread-store.ts` persiste hilos versionados en
`localStorage`, con tolerancia a datos corruptos, a la cuota del navegador y a
contextos donde el almacenamiento no está disponible.

**Un botón alterna entre el chat y el modo administrador**, que expone la
ingesta por API con su progreso en vivo.

## Comandos

```bash
pnpm install          # instalar
pnpm dev              # http://127.0.0.1:5173
pnpm build            # build de producción
pnpm typecheck        # tsc -b --noEmit
pnpm lint             # eslint, cero warnings
pnpm test             # vitest run
pnpm e2e              # playwright
pnpm openapi:gen      # regenerar src/types/api.gen.ts
pnpm openapi:check    # regenerar y fallar si hay diferencias
```

Desde la raíz del repositorio: `make check-frontend` encadena lint, typecheck,
tests y build.

Playwright usa el Chrome estable del sistema (`channel: 'chrome'`) para no
descargar binarios propios, y arranca el servidor de desarrollo por su cuenta.
El smoke necesita además el backend en marcha: las tarjetas de sugerencia
salen de `GET /api/v1/demo/cases`.

## Tipos del API

`src/types/api.gen.ts` se genera desde `docs/api/openapi.json` y **no se
versiona**. Se regenera automáticamente antes de `dev`, `build` y `test`
mediante los hooks `predev`, `prebuild` y `pretest`: pnpm no ejecuta
`postinstall` con `--frozen-lockfile`, así que no se puede depender de él para
mantener los tipos frescos.

La ruta del `openapi.json` se puede sobrescribir con `OPENAPI_JSON_PATH`
(por defecto, `../../docs/api/openapi.json` relativa a `frontend/`).

## Variables de entorno

| Variable | Por defecto | Descripción |
|---|---|---|
| `VITE_API_BASE_URL` | `""` | URL base del backend. Vacío = mismo origen. |
| `MODE`, `DEV`, `PROD` | según Vite | establecidas por Vite |

No hay secretos en el bundle: la autenticación la gestiona el proxy inverso, y
el despliegue sirve la SPA y `/api/v1/*` desde el mismo origen. En desarrollo,
`vite.config.ts` redirige `/api/v1` y `/health` al backend en `:8000`, de modo
que el código del cliente sigue hablando de mismo origen en los dos entornos.
