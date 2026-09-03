# API HTTP

Contrato del backend FastAPI. La especificación completa está en
[`api/openapi.json`](api/openapi.json), que es además la fuente desde la que
el frontend genera sus tipos: un cambio de contrato sin regenerar rompe el
`typecheck`.

Con el backend en marcha, el explorador interactivo está en
<http://127.0.0.1:8000/docs>.

## Superficie

| Método | Ruta | Para qué |
|---|---|---|
| `POST` | `/api/v1/queries` | sobre unificada: los tres modos en una respuesta |
| `POST` | `/api/v1/queries/stream` | la misma sobre, por Server-Sent Events |
| `POST` | `/api/v1/queries/resolve` | sólo el router automático (enum cerrado) |
| `POST` | `/api/v1/questions/answer` | flujo documental explícito |
| `POST` | `/api/v1/claims/analyze` | flujo de siniestros explícito |
| `GET` | `/api/v1/manual` | manual activo y sus metadatos |
| `GET` | `/api/v1/manual/pdf?version=<sha256>` | el PDF original |
| `GET` | `/api/v1/manual/evidence/{evidence_id}` | una página como evidencia |
| `GET` | `/api/v1/demo/cases` | casos de demostración curados |
| `GET`/`POST` | `/api/v1/admin/ingestion` | estado y lanzamiento de la ingesta |
| `GET` | `/api/v1/admin/ingestion/events` | progreso de la ingesta (SSE) |
| `GET` | `/api/v1/admin/ingestion/extractions` | publicaciones disponibles |
| `GET` | `/health/live` | proceso vivo |
| `GET` | `/health/ready` | índice publicado y alias activo |

Las rutas se montan según lo que la raíz de composición haya inyectado: la
sobre unificada aparece sólo si están los tres puertos, y la variante SSE
además requiere `sse-starlette`. Sin esa dependencia el camino síncrono sigue
funcionando en lugar de romper el arranque.

## La sobre unificada

### Petición

```json
{
  "text": "Un vehículo cambia de carril y golpea al que circulaba por el carril contiguo.",
  "mode": "auto",
  "language": "es",
  "profile": "baseline",
  "clarifications": null,
  "session_id": "…",
  "thread_id": "…",
  "resume": false
}
```

- `mode`: `question`, `claim` o `auto`. Los modos explícitos **no** pasan por
  el router.
- `clarifications`: sólo se admite con `mode=claim`; es la respuesta a una
  entrevista abierta previamente. Con cualquier otro modo, 422.
- `profile`: se valida contra el catálogo de `backend/configs/`. Un perfil
  desconocido devuelve 422 con `code=unsupported_profile`.
- `session_id` / `thread_id`: identidad de conversación; `session_id` viaja
  hasta los metadatos de Langfuse para agrupar las trazas de un hilo.

### Respuesta

```json
{
  "request_id": "…",
  "requested_mode": "auto",
  "resolved_mode": "claim",
  "result": { "kind": "claim", "…": "…" },
  "evidence": [
    { "evidence_id": "sha256:b9c7…:page:57",
      "document_hash": "b9c7…", "pdf_page": 57, "delivery": "text" }
  ],
  "metadata": { "trace_id": "…", "langfuse_url": "…" }
}
```

`result.kind` es un literal cerrado con tres variantes; el frontend hace
`switch` sobre él con un `default` imposible por tipos.

**`kind: "question"`**

```
status : answered | partial | insufficient_evidence | out_of_scope
blocks : [{ text, evidence_ids }]
trace_id, trace_url
```

**`kind: "claim"`**

```
applicability : applicable | not_applicable | undetermined
convention    : CIDE | ASCIDE | null
decision      : resolved | conditional | undetermined | not_assessed
party_ids, facts, contradictions, conditions, missing_information, blocks
rules_evaluated : cada regla que corrió, con entradas, resultado y evidencia
trace_id, trace_url
```

**`kind: "clarification"`**

```
message        : la pregunta concreta
missing_fields : los datos que faltan
```

`evidence` nunca expone rutas de fichero: sólo la identidad de la página, que
el cliente resuelve contra `/api/v1/manual/pdf`. `metadata.langfuse_url` es
`null` cuando no se puede construir un enlace real; el frontend oculta el
enlace en lugar de ofrecer uno que devuelve 404.

## Streaming

`POST /api/v1/queries/stream` acepta el mismo cuerpo y emite cuatro tipos de
evento:

| Evento | Cuándo |
|---|---|
| `started` | al aceptar la petición, con sus metadatos |
| `stage` | sólo en `mode=auto`, cuando el router resuelve el modo |
| `completed` | con la sobre completa |
| `failed` | con el error acotado |

Cada evento lleva un `event_id` nuevo, un `timestamp` ISO-8601 y **el mismo
`request_id`** que los demás eventos de la petición, para que el cliente pueda
coserlos y calcular duraciones reales por etapa. No hay reintento automático:
un `failed` es final.

Los modos explícitos nunca emiten `stage`; una resolución a `clarification`
tampoco, porque no hay etapa que reportar.

## Errores

Un fallo durante el streaming llega como evento `failed` con esta forma:

```json
{ "code": "internal_error", "message": "…",
  "request_id": "…", "retryable": true }
```

`code` es un literal cerrado (`ErrorResponse` en
`schemas/errors.py`): `invalid_request`, `unsupported_profile`,
`unsupported_mode`, `unsupported_language`, `provider_timeout`,
`provider_unavailable`, `internal_error`. El mensaje se recorta a 200
caracteres y no se exponen trazas internas.

Un perfil no reconocido se rechaza antes de ejecutar nada, con 422 y
`detail = {"code": "unsupported_profile", "profile": "…"}`, tanto en la ruta
síncrona como en la de streaming.

`insufficient_evidence` **no** es un código de error: es un estado de una
respuesta 200. Que el sistema se abstenga con criterio no es un fallo.

## Casos de demostración

`GET /api/v1/demo/cases` sirve una selección curada leída del golden set real,
sin exponer nunca `expected_output`. Los cinco casos cubren los
comportamientos que hay que poder enseñar: dos consultas documentales, un
siniestro que se resuelve, uno en el que abstenerse es lo correcto y una
pregunta fuera de alcance.

## Modo administrador de ingesta

`POST /api/v1/admin/ingestion` lanza la ingesta del manual verificado y
publica el índice de forma atómica; `GET .../events` retransmite el progreso
por SSE y `GET .../extractions` lista las publicaciones disponibles. La ingesta
por API sólo acepta el documento verificado y opera con el parser `pypdf`.

## Salud

`/health/live` responde siempre que el proceso esté vivo. `/health/ready`
devuelve 200 sólo si la sonda de índice confirma que el alias
`allianz-manual-active` está publicado; en cualquier otro caso, 503. Una
composición que no inyecte una sonda real se queda en 503 antes que afirmar
una disponibilidad que no ha comprobado.
