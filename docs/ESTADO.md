# Estado del proyecto — punto de entrada único

**Última verificación independiente: 2026-09-02.** Este documento es el índice único de estado. Las afirmaciones de ejecución se apoyan en los comandos del corte; cualquier documento que las contradiga queda superado. Los planes activos se limitan al enlazado abajo; el resto es histórico.

Si retomas el trabajo, lee **sólo esto y el plan vigente**. No hace falta reconstruir el historial desde los handoffs antiguos: su contenido válido está incorporado aquí.

## Qué es este proyecto

Prueba técnica de Allianz (`GenAI_Interview_Instructions.docx`, SHA-256 `8561213339f76c7bd8a6c56fa0c91323c6d838ae0e9d0f30a12d8e3f775a4957`): un sistema RAG sobre el manual CIDE/ASCIDE/CICOS que responde preguntas del manual y analiza relatos de accidentes.

Fuente documental: `data/raw/Manual-cide-ascide-y-cicos.pdf`, 111 páginas, SHA-256 `b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344`, edición de **noviembre de 2004**. No es derecho vigente y nunca debe presentarse como tal.

## Documentos vigentes

| Documento | Papel |
|---|---|
| **`docs/ESTADO.md`** (este) | Punto de entrada. Estado verificado y índice. |
| **`docs/superpowers/plans/2026-09-02-cierre-verificado.md`** | **Plan vigente.** Seis tareas ordenadas por evidencia y entrega. |
| `docs/superpowers/specs/2026-08-31-allianz-rag-design.md` | Especificación de diseño. Autoridad sobre alcance y contratos. |
| `docs/architecture/2026-08-31-api-y-experiencia-propuesta.md` | Anexo de la spec: API, estados y experiencia. |
| `docs/architecture/2026-08-31-stack-tecnologico-propuesto.md` | Anexo de la spec: stack y fronteras. |
| `docs/evaluation/2026-08-31-golden-set-y-metricas-rag.md` | Anexo de la spec: protocolo de golden y métricas. |
| `docs/evaluation/annotation-guide.md` | Taxonomía y flujo de anotación del golden. |
| `docs/evaluation/coverage-matrix.md` | Diseño de cobertura del golden. Sin casos admitidos todavía. |
| `docs/evaluation/golden-set-source-map.md` | Mapa de evidencias de los cinco siniestros. Verificado contra `pages.jsonl`. |
| `docs/rules/transcription-protocol.md` | Protocolo de doble transcripción de la matriz. |
| `docs/ingestion-baseline.md`, `docs/ingestion/parser-comparison.md` | Extracción baseline y comparativa de parsers. |
| `docs/operations/local-services.md` | Operación de los servicios locales. |
| `docs/enunciado/GenAI_Interview_Instructions.docx` | Enunciado original, tal como se recibió. |
| `README.md`, `backend/README.md`, `frontend/README.md` | Puesta en marcha. |

## Documentación retirada

Los handoffs, planes e informes de corte que se contradecían o duplicaban el estado se
han eliminado. Git conserva su historial. El índice, la especificación y el plan vigentes
son suficientes para retomar la entrega sin reconstruir sesiones anteriores.

## Estado verificado (2026-09-02)

### Gates

| Gate | Resultado medido |
|---|---|
| `make test-backend` | **408 passed**, 1 skipped, 2 warnings (ejecución 2026-09-02; salida 0) |
| `make lint-backend` | OK (corregido el 2026-09-02 tras ordenar el bloque de imports de `test_daa_circumstances.py`) |
| `make check-frontend` | lint + typecheck + **92 tests** + build, OK |
| `make check-openapi` | OK |

Lint, formato, tipado estricto, frontend y OpenAPI están verdes en este corte. La suite backend completa terminó con salida 0 en la última ejecución.

`make serve-backend` arranca desde un entorno limpio: mapea las claves de Langfuse desde
`ops/local.env` y aprovisiona los prompts numerados con `make provision-prompts`.

Nota histórica: algunos cortes anteriores de `make check-backend` terminaron con `Error 134` por un teardown de torch (`libc++abi`); la última ejecución de `make test-backend` terminó con salida 0.

`make typecheck-backend` termina con **0 errores, 0 warnings, 0 informations**. La deuda de Pyright estricto quedó eliminada sin bajar severidad ni añadir ignores generales.

### Git

Rama `main`. En el corte anterior a este catálogo, `HEAD` y `origin/main` estaban en `ac6efe8`.
Esta actualización se versiona y publica como parte de la misma sesión.

Sesión única: no hay otros agentes trabajando en el repositorio.

### Servicios

Compose `allianz-rag` usa el contexto Docker activo, verificado como `desktop-linux` el 2026-09-02. Langfuse, langfuse-worker, ClickHouse, PostgreSQL, Redis, Qdrant y MinIO están arriba; `make doctor` confirma Qdrant y Langfuse sanos. El anterior stack y sus volúmenes de `colima-allianz` se eliminaron antes de recrearlo.

### Qué está hecho

- **Ingestión**: contrato de publicación unificado; pypdf y Docling publican `original.pdf`. CLI `compare-parsers`. Páginas en blanco preservadas.
- **Perfiles e índices**: `IndexSignature` con 13 campos; CLI `index-rollback` y `list-index-versions`; `rollback_alias` verifica firma antes de mover el alias.
- **Recuperación**: densa + BM25 español + RRF nativo de Qdrant, intercambiables por configuración.
- **Workflows**: grafo documental (`retrieve → generate → validate`) y grafo de siniestros (`extract_facts → retrieve_criteria → apply_rules → explain → validate`). La extracción del LLM no puede sobrescribir el resultado determinista.
- **Reglas de aplicabilidad**: `domain/rules/applicability.py` implementa la puerta de dos vehículos, colisión directa, tercero identificado y colisión en cadena, con evidencia obligatoria. Verificado.
- **Catálogo D.A.A.**: `data/rules/daa-circumstances.v1.json` fija y versiona las etiquetas `A0`–`A17`. El responsable del proyecto validó la correspondencia el 2026-09-02. Es una fuente externa al manual: `A0` significa ausencia de circunstancia declarada y `A1`–`A17` son las 17 casillas del apartado 12 del parte amistoso.
- **API**: sobre común tipado, JSON y SSE para consultas, más el modo administrador de ingesta por API (`GET/POST /api/v1/admin/ingestion`, eventos y extracciones paginadas). La ingesta sólo acepta el manual verificado y publica el índice de forma atómica; el CLI técnico queda para mantenimiento, evaluación, validación y CI. Los eventos llevan `event_id` y `timestamp`, y `dispatch` sólo se emite en modo `auto` (`73516e1`).
- **Frameworks de calidad**: CLI `golden validate/freeze/publish`, CLI `rules validate/compare-transcriptions`, schemas de matriz y ruleset con attestation obligatoria, validación de releases que rechaza `technical_fixture` por defecto.
- **Frontend**: React 19 + Vite, chat con tool calls, visor PDF, 92 tests unitarios, build limpio. El botón superior alterna entre modo administrador y volver al chat; en administración se oculta la columna de hilos y el estado publicado no mantiene animación de carga.
- **Historial real** (`df71fbe`): `lib/thread-store.ts` persiste hilos versionados en localStorage
  (`cicos.threads.v1`) con tolerancia a datos corruptos, cuota y sandbox. Cada hilo lleva un
  `session_id` estable. Sustituye a los hilos falsos. *(El docstring de `thread-sidebar.tsx:18`
  todavía dice «mock (5 hardcoded)»: es un comentario obsoleto, no el comportamiento.)*
- **Visor PDF** (`bb6c1a5`): cierre único y fallback explícito a página cuando no hay región
  verificada.

### Qué falta — los agujeros reales

Ordenados por impacto sobre la entrega.

1. **Los tres entregables de demo del plan no existen**: documento de arquitectura, presentación y guion reproducible. El enunciado exige explícitamente los dos primeros. → Task 5 del plan.
2. ~~`data/rules/` sólo tiene los schemas.~~ **HECHO.** La matriz 18×18, el ruleset de 14 reglas y el catálogo D.A.A. `A0`–`A17` están versionados. La matriz permanece protegida: sólo puede aplicarse cuando haya casillas A y B declaradas de forma inequívoca; una narración ambigua no autoriza a inferirlas.
3. **`data/evaluation/golden/` está vacío** (sólo `releases/`). Sin golden no hay comparativa de recuperación, ni métricas de router, ni holdout. → Tasks 4, 5.
4. **`data/extractions/` sólo contiene `pypdf-6.16.2`.** Sin la publicación Docling no hay bounding boxes y el visor no puede resaltar región. → Pendiente de ingesta estructurada; no es una tarea separada del plan vigente.
5. **`session_id` existe en el frontend pero no en el backend.** `thread-store.ts` ya asigna uno estable por hilo (`df71fbe`), pero `backend/src` **no tiene ninguna ocurrencia** de `session_id`: no lo recibe ni lo propaga a Langfuse, así que las conversaciones siguen sin agruparse. Es media integración. → Task 2.
6. **El frontend fabrica duraciones.** El backend ya envía `timestamp` por evento; `frontend/src/lib/thread-state.ts` lo ignora y escribe `durationMs: 0` a mano en las líneas 505 y 516. → Pendiente fuera del desglose actual del plan.
7. **Falta `GET /api/v1/demo/cases`**, la única capacidad HTTP de la spec sin implementar. → Task 3.
8. **OpenAPI está sincronizado**: `make check-openapi` pasó en el corte actual.

9. **Modo administrador e ingesta por API**: implementado y probado. La interfaz sustituye “Nueva consulta” por “Modo administrador”, muestra estado, etapas y previsualizaciones de extracciones en un desplegable con paginación. La ejecución real del 2026-09-02 completó las cuatro etapas, verificó el hash `b9c70c…c8344`, registró 111 páginas y publicó 118 fragmentos en Qdrant; `/health/ready` quedó `ready`. Estos datos son de esta ejecución operativa, no métricas de evaluación.

### Limitaciones que hay que declarar, no resolver

- **El manual no define qué maniobra es `A0`…`A17`.** Son casillas del apartado 12 del parte amistoso europeo (D.A.A.), un formulario externo al manual. Cualquier catálogo que las traduzca es de procedencia externa y el sistema no puede citar el manual como su fuente.
- **Cuatro de los cinco siniestros del enunciado caen fuera del Convenio.** Abstenerse con criterio es la respuesta correcta, y la spec lo recoge: «no se exige inventar una conclusión definitiva».
- **La alcoholemia no excluye el Convenio** (p. 9 del manual). Lo penal y los daños personales sí quedan fuera del alcance convencional.
- El manual es de 2004.

## Decisiones vigentes

1. Backend es la única fuente de verdad de etapas, timestamps y duraciones.
2. La matriz 18×18 no se autotranscribe desde tablas de Docling. Exige dos transcripciones independientes y adjudicación humana firmada.
3. `technical_fixture` se rechaza por defecto en cualquier release real.
4. El holdout se abre una sola vez, tras congelar código, prompts y reglas.
5. No se inventan métricas, trazas, tiempos, reglas evaluadas ni resultados.
6. Todo artefacto experimental identifica commit, hashes, perfil, prompts y modelos.

## Decisiones humanas pendientes

Están marcadas como PARADAS bloqueantes en el plan vigente:

1. ~~Adjudicar las divergencias entre las dos transcripciones de la matriz y firmar la attestation.~~ **HECHO.**
2. ~~Validar el catálogo de las 18 circunstancias de la D.A.A. (Task 2, Step 7)~~ **HECHO el 2026-09-02.**
3. Revisar la anotación de los cinco siniestros antes de marcarlos `adjudicated`. (Task 4, Step 3)
