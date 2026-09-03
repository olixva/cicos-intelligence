# Operación local

Cómo levantar el sistema completo, qué necesita y cómo comprobar que está
sano.

## Requisitos

| | |
|---|---|
| Python | 3.14, gestionado por [uv](https://docs.astral.sh/uv/) |
| Node | ≥ 20.18, con pnpm 9 (el Makefile lo invoca vía `npm exec`) |
| Docker | con Compose v2 |
| OpenAI | una clave de API con acceso a la Responses API y a embeddings |

## Servicios locales

`compose.yaml` levanta la pila de observabilidad y el vector store:

| Servicio | Puerto | Para qué |
|---|---|---|
| Qdrant | 6333 | índice vectorial + BM25 |
| Langfuse (web) | 3000 | trazas, prompts versionados, datasets |
| langfuse-worker | — | procesado asíncrono de Langfuse |
| PostgreSQL | — | metadatos de Langfuse |
| ClickHouse | — | almacenamiento analítico de Langfuse |
| Redis | — | colas de Langfuse |
| MinIO | — | blobs de Langfuse |

Sólo Qdrant y Langfuse publican puerto en `127.0.0.1`; el resto es interno a
la red de Compose.

```bash
cp ops/local.env.example ops/local.env   # y rellena las credenciales
make local-services-config               # valida compose.yaml contra ops/local.env
make local-services-up                   # docker compose up -d
make local-services-stop                 # parar sin borrar volúmenes
```

`ops/local.env` contiene las credenciales de la pila (Postgres, ClickHouse,
Redis, MinIO, la organización y el proyecto de Langfuse, y sus claves de API).
Está fuera del control de versiones.

## Variables de entorno de la aplicación

`cp .env.example .env` y rellena. Las que importan:

| Variable | Para qué |
|---|---|
| `OPENAI_API_KEY` | acceso a la API de OpenAI |
| `OPENAI_ANSWER_MODEL` | generación de la respuesta documental |
| `OPENAI_CLAIM_EXTRACTION_MODEL` | extracción de hechos del siniestro |
| `ALLIANZ_ROUTER_MODEL` | clasificador del modo automático |
| `QDRANT_URL` / `ALLIANZ_QDRANT_URL` | Qdrant y su sonda de disponibilidad |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | claves del proyecto local |
| `LANGFUSE_BASE_URL` / `LANGFUSE_PROJECT_ID` | base y **id** (no nombre) del proyecto |
| `ALLIANZ_DOCUMENT_HASH` | SHA-256 del manual verificado |
| `ALLIANZ_EXTRACTIONS_ROOT` / `ALLIANZ_EVIDENCE_PARSER` | publicación de evidencia que sirve el API |
| `ALLIANZ_RULES_ROOT` | artefactos de reglas firmados |
| `ALLIANZ_DOCLING_ARTIFACTS` | bundle local de modelos de Docling (opcional) |

### Reparto de modelos

Los tres niveles de GPT-5.6 son capacidades, no variantes, con un factor ~25×
de precio entre el mayor y el menor. El reparto por defecto sigue el coste de
equivocarse en cada etapa:

- **Respuesta documental → `gpt-5.6-sol`.** Es la etapa que se juzga: citas
  estrictas sobre el contexto y abstención cuando no hay evidencia.
- **Extracción de hechos → `gpt-5.6-terra`.** Extracción estructurada acotada,
  más fácil que generar la respuesta pero exige precisión.
- **Router → `gpt-5.6-luna`.** Clasificación en un enum cerrado, alto volumen,
  tarea trivial.

Para una tanda de evaluación masiva se bajan las tres a `gpt-5.6-luna`.

## Puesta en marcha desde cero

```bash
make local-services-up   # 1. Qdrant y Langfuse
make verify-source       # 2. SHA-256 y legibilidad del manual
make index-baseline      # 3. índice en Qdrant + alias `allianz-manual-active`
make doctor              # 4. comprobar
```

`index-baseline` carga `.env` igual que `serve-backend`, así que no hace falta
exportar `OPENAI_API_KEY` a mano. Publica una colección nueva y mueve el alias
al terminar; la anterior se conserva para poder volver a ella con
`allianz index-rollback`.

No hace falta reingerir: la publicación baseline (`pypdf-6.16.2`) viene
versionada en `data/extractions/`, junto al manual original. Reingerir o usar
la ingesta estructurada con Docling es opcional y está descrito en
[ingesta-y-recuperacion.md](ingesta-y-recuperacion.md).

## Día a día

```bash
make local-services-up   # si no están levantados
make serve-backend       # aprovisiona prompts y arranca uvicorn en :8000
make serve-frontend      # vite con HMR en :5173
```

```
http://127.0.0.1:5173/          interfaz de chat
http://127.0.0.1:8000/docs      Swagger del API
http://127.0.0.1:3000/          Langfuse
http://127.0.0.1:6333/dashboard Qdrant
```

`serve-backend` depende de `provision-prompts`, que crea de forma idempotente
los prompts numerados que el API espera (`document-question`, `auto-router`).
Sin ellos, un entorno recién levantado arrancaba y fallaba con «Prompt not
found»; el objetivo del Makefile cierra ese hueco y nunca sobrescribe una
versión existente.

El mismo objetivo carga `.env` y mapea las claves de Langfuse desde
`ops/local.env`, donde Compose las define con prefijo `ALLIANZ_`.

## Verificación

```bash
make check-all        # backend + frontend + contratos OpenAPI
make check-backend    # ruff + formato + pyright + pytest
make check-frontend   # eslint + tsc + vitest + build
make check-openapi    # el openapi.json publicado no ha derivado del código
make test-e2e         # Playwright contra la aplicación real
```

`check-openapi` compara el esquema que produce el código con
`docs/api/openapi.json` y, del lado del frontend, regenera los tipos y falla si
hay diferencias. Es lo que impide que el contrato y el cliente se separen en
silencio.

## Diagnóstico

```bash
make doctor                          # servicios locales
allianz doctor --operation retrieval  # sólo Qdrant
allianz doctor --operation evaluation # sólo Langfuse
allianz doctor --operation all        # todo
```

Devuelve booleanos de disponibilidad y metadatos públicos de endpoint. Las
credenciales se comprueban por presencia; sus valores nunca se devuelven, y no
se hace ninguna llamada a un proveedor de modelos.

## Docker

Ambas partes tienen imagen propia como alternativa al entorno local:

```bash
docker build -t allianz-backend -f backend/Dockerfile .
docker build -t allianz-frontend -f frontend/Dockerfile .
docker run --rm -p 8000:8000 --env-file ops/local.env allianz-backend
docker run --rm -p 5173:5173 allianz-frontend
```
