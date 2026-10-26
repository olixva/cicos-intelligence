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
| `LANGFUSE_BASE_URL` / `LANGFUSE_PROJECT_ID` | base local (`127.0.0.1:3000`; en Docker `host.docker.internal:3000`) e **id** (no nombre) del proyecto |
| `ALLIANZ_DOCUMENT_HASH` | SHA-256 del manual verificado |
| `ALLIANZ_EXTRACTIONS_ROOT` / `ALLIANZ_EVIDENCE_PARSER` | publicación de evidencia que sirve el API |
| `ALLIANZ_RULES_ROOT` | artefactos de reglas firmados |
| `ALLIANZ_DOCLING_ARTIFACTS` | bundle local de modelos de Docling (opcional) |
| `TYPESAFE_API_KEY` | acceso requerido por los defaults Jev de router y guardarraíl |
| `ALLIANZ_ROUTER_BACKEND` | `jev` (por defecto) o `openai` para el modo automático |
| `ALLIANZ_INPUT_GUARD` | `jev` (por defecto) o `off` para desactivar el guardarraíl semántico |

### Reparto de modelos

Los defaults propuestos siguen el coste de equivocarse en cada etapa y el
catálogo oficial de [modelos OpenAI](https://developers.openai.com/api/docs/models):

- **Respuesta documental → `gpt-6.1-sol`.** Etapa juzgada por citas y abstención.
- **Extracción de hechos → `gpt-6.1-sol`.** Se conserva Sol como default
  conservador hasta comparar Luna con el golden.
- **Router OpenAI de referencia → `gpt-6-luna`.** Clasificación en enum cerrado;
  se selecciona con `ALLIANZ_ROUTER_BACKEND=openai`.

- **Router predeterminado → Jev (`jev-latest`, umbral 0,4).** En el golden de
  110 casos Jev y OpenAI Luna acertaron 97/110 (88,2 %) cada uno, sin errores
  tras reanudar una llamada OpenAI que agotó el timeout. OpenAI sigue disponible
  seleccionando `ALLIANZ_ROUTER_BACKEND=openai`.

Los IDs de `.env.example` son defaults de configuración. El humo sintético de
Responses API con `gpt-6-luna` pasó para respuesta, extracción y router; Sol no
se probó y la extracción sólo se cambiará a `gpt-6-luna` si la comparación no
añade resoluciones injustificadas ni una regresión material de seguridad.

### Modelo de decisiones (Jev)

[Jev](https://typesafe.ai) es un modelo discriminativo de TypeSafe: no genera
texto, responde preguntas tipadas sobre un estado (probabilidad de sí, elección
entre opciones cerradas). Encaja donde el trabajo es decidir sobre un conjunto
cerrado, y se ha integrado en tres sitios. Router y guardarraíl son los
defaults validados; el juez de evaluación permanece opt-in:

| Uso | Activación | Qué hace |
|---|---|---|
| Router del modo `auto` | default `jev`; `ALLIANZ_ROUTER_BACKEND=openai` selecciona OpenAI | Una pregunta `choice` entre `question`, `claim` y `clarification_required`; por debajo del umbral 0,4 pide aclaración. No carga el prompt `auto-router`. |
| Guardarraíl de entrada | default `jev`; `ALLIANZ_INPUT_GUARD=off` lo desactiva | Dos preguntas `noul` (intento de manipular al asistente; consulta ajena al dominio) que bloquean por encima de umbral, tras el filtro por expresiones regulares. **Falla abierto**: si Jev no responde, la petición sigue y se deja un aviso en el log. |
| Juez de evaluación | `run_baseline.py --judge jev` | Añade *context precision* y *groundedness* al runner (ver `evaluacion.md`). |

El cliente (`infrastructure/adapters/outbound/decision_model/jev_client.py`) usa
`httpx` contra `POST /v1/systemone` con el contrato del OpenAPI del SDK oficial,
y reutiliza `TYPESAFE_API_KEY`, `TYPESAFE_BASE_URL` y `TYPESAFE_DEFAULT_MODEL`.
Reintenta 408/429/5xx con espera acotada y respeta `Retry-After`; los errores
técnicos usan la jerarquía de `LanguageModelError`, de modo que la API los
traduce igual que los del LLM.

**Estado: verificado contra el servicio real con datos sintéticos y el golden.**
El cliente respondió `noul` y `choice`; en el golden, Jev y OpenAI Luna
acertaron 97/110 (88,2 %) con umbral Jev 0,4 y sin errores tras reintentar una
llamada OpenAI agotada. En tres campañas red-team actuales, Jev+guard `off`,
Jev+guard Jev y OpenAI Luna+guard Jev registraron 0/27 ataques exitosos y
0/3 controles benignos rechazados en cada configuración. Por tanto, esta suite
no demuestra una mejora del guard frente a `off`; sólo muestra que ninguna de
las tres variantes vulneró estos casos sintéticos. Jev sigue siendo el default
tipado; OpenAI y `off` son overrides explícitos. No hay fallback silencioso.
Los umbrales requieren recalibración si cambia el golden.
TypeSafe publica que no entrena con solicitudes/respuestas; la retención depende
de los datos, los acuerdos aplicables y cualquier opción Zero Data Retention
(ZDR) acordada. El servicio se aloja en Estados Unidos, y ZDR está disponible
para clientes Enterprise previa configuración. Antes de usar relatos reales,
hay que revisar el contrato y DPA de la cuenta, confirmar ZDR si se requiere y
resolver la transferencia internacional aplicable. Véanse la
[guía de tratamiento y retención de TypeSafe](https://help.typesafe.ai/articles/5974925716-how-is-submitted-data-used-or-retained),
su [política de privacidad](https://typesafe.ai/legal/privacy-policy) y la
[oferta Enterprise](https://typesafe.ai/enterprise). No se afirma que esos
controles estén contratados o configurados para este prototipo.

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

Para el golden y el red-team, usa `make run-baseline ARGS="..."` y
`make run-redteam ARGS="..."`: ambos cargan `.env` y `ops/local.env` igual que
`make serve-backend`. Si una campaña necesita valores distintos, pasa las
mismas asignaciones con `LOCAL_ENV` a los dos objetivos para que sus manifiestos
describan la configuración del servicio.

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
ALLIANZ_BUILD_COMMIT=$(git rev-parse HEAD)
ALLIANZ_BUILD_FINGERPRINT=$(uv run --project backend --no-sync python -c 'import sys; from pathlib import Path; sys.path.insert(0, "backend/src"); from application.services.evaluation_runtime_config import evaluation_build_fingerprint; print(evaluation_build_fingerprint(Path.cwd()))')
docker build \
  --build-arg "ALLIANZ_BUILD_COMMIT=$ALLIANZ_BUILD_COMMIT" \
  --build-arg "ALLIANZ_BUILD_FINGERPRINT=$ALLIANZ_BUILD_FINGERPRINT" \
  -t allianz-backend -f backend/Dockerfile .
docker build -t allianz-frontend -f frontend/Dockerfile .
docker run --rm -p 8000:8000 --env-file .env --env-file ops/local.env \
  -e QDRANT_URL=http://host.docker.internal:6333 \
  -e ALLIANZ_QDRANT_URL=http://host.docker.internal:6333 \
  -e LANGFUSE_BASE_URL=http://host.docker.internal:3000 \
  -v "$PWD/data:/app/data:ro" \
  -v "$PWD/data:/app/backend/data:ro" allianz-backend
docker run --rm -p 5173:5173 allianz-frontend
```

El contenedor backend mantiene su caché de `uv` bajo `/tmp/uv-cache` para
arrancar como usuario sin privilegios. `host.docker.internal` sólo se acepta
como alias local de Docker para Langfuse; los endpoints remotos se rechazan.
La imagen recibe el commit y la huella del código como argumentos de build,
porque no contiene `.git`; ambos aparecen en `/health/config` sin exponer
credenciales. El 26-10-2026 se construyó
`allianz-backend:tfm-final-20261026` desde el commit `2f31e866` con la huella
`f9e6a230efee0209…`. `/health/ready` devolvió `ready`; `/health/config` mostró
esa misma procedencia, Jev y Luna, el hash del manual y el índice activo de 118
puntos. Una petición sintética por modo (`question`, `claim`, `auto`) devolvió
HTTP 200; `claim` pidió aclaraciones y conservó el metadato de traza. El smoke
usó un puerto y contenedor aislados y no reinició los servicios locales.
