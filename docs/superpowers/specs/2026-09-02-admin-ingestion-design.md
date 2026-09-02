# Modo administrador e ingesta por API

Fecha: 2 de septiembre de 2026. Estado: implementado y verificado en el worktree actual.

## Objetivo

Permitir que la demo reingeste el único manual de la prueba desde un botón de la interfaz principal, sin depender de CLI para la operación. La pantalla mostrará el estado persistido, las fases reales, el resumen de extracciones y el resultado de la publicación del índice.

## Alcance y límites

- La única fuente admitida es `data/raw/Manual-cide-ascide-y-cicos.pdf` con SHA-256 `b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344`.
- No se aceptan cargas de archivos, rutas suministradas por el cliente, parsers arbitrarios ni documentos externos.
- El CLI se conserva para mantenimiento, evaluación, validación y CI cuando no exista una acción segura de interfaz. Ningún flujo normal de la demo dependerá de él.
- El índice activo no cambia durante una ejecución. Sólo una publicación atómica completada puede sustituirlo.
- El manual es una edición de noviembre de 2004 y no se presenta como derecho vigente.

## Experiencia de usuario

El control superior derecho “Nueva consulta” pasa a ser “Modo administrador”. Al activarlo se muestra un panel dedicado, coherente con la estética actual, con:

- estado del índice y de la última ejecución;
- hash, edición, páginas, fragmentos, parser y colección, sólo si el backend los ha producido;
- botón “Reingestar manual”;
- etapas: verificar manual, extraer/publicar evidencia y construir/publicar índice;
- resumen paginado de las páginas extraídas y enlace al visor PDF existente;
- error seguro y posibilidad de volver al chat sin perder los hilos.

## Contrato HTTP

`GET /api/v1/admin/ingestion` devuelve el último job persistido y la ejecución activa, si existe.

`POST /api/v1/admin/ingestion` inicia una ejecución. Si hay una activa devuelve `409`; el servidor no arranca una segunda. La respuesta contiene el `job_id` y el estado inicial.

`GET /api/v1/admin/ingestion/events` entrega SSE para la ejecución activa. Cada evento incluye `event_id`, `timestamp`, `job_id`, etapa, estado y datos públicos ya producidos. No incluye stack traces, secretos ni rutas internas.

`GET /api/v1/admin/ingestion/extractions?offset=&limit=` devuelve un resumen paginado de páginas publicadas: identificador de evidencia, número de página, hash y disponibilidad de regiones. El PDF sigue sirviéndose por la ruta manual existente.

## Modelo de ejecución

`IngestionJob` persistido localmente contiene: id, estado (`idle`, `running`, `succeeded`, `failed`), etapa actual, timestamps, hash esperado/validado, parser, páginas, fragmentos, colección, error público y eventos. El almacenamiento debe sobrevivir a una recarga del navegador y no requiere introducir una base de datos nueva para esta prueba.

El worker reutiliza los casos de uso y adaptadores actuales (`build_ingest_document` y `build_and_publish_retrieval_index`) como composición interna de la API; no llama a un subproceso CLI. La publicación del índice continúa siendo atómica.

## Errores y concurrencia

Un PDF con hash inesperado, una extracción incompleta o un fallo de Qdrant deja la ejecución como `failed`, conserva el índice anterior y muestra un mensaje accionable sin detalles internos. El endpoint de inicio usa un lock/protección equivalente para impedir doble ejecución.

## Verificación

- Pruebas backend: estados, conflicto concurrente, hash inválido, persistencia, eventos SSE y resumen de extracciones.
- Pruebas frontend: botón, panel, reconexión/estado terminado, error y retorno al chat.
- Gates: `make typecheck-backend`, `make lint-backend`, `make check-frontend`, `make check-openapi`, `make test-e2e` y ensayo visual local.
- No se declararán métricas de evaluación por el hecho de reingerir.
