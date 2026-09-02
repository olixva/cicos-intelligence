# Estado del proyecto — punto de entrada único

**Última verificación: 2026-09-02.** Este documento es la **única fuente de verdad** sobre el estado del proyecto. Cualquier otro documento que contradiga a este está superado; los superados viven en `docs/archive/` con su aviso correspondiente.

Si retomas el trabajo, lee **sólo esto y el plan vigente**. No hace falta reconstruir el historial desde los handoffs antiguos: su contenido válido está incorporado aquí.

## Qué es este proyecto

Prueba técnica de Allianz (`GenAI_Interview_Instructions.docx`, SHA-256 `8561213339f76c7bd8a6c56fa0c91323c6d838ae0e9d0f30a12d8e3f775a4957`): un sistema RAG sobre el manual CIDE/ASCIDE/CICOS que responde preguntas del manual y analiza relatos de accidentes.

Fuente documental: `data/raw/Manual-cide-ascide-y-cicos.pdf`, 111 páginas, SHA-256 `b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344`, edición de **noviembre de 2004**. No es derecho vigente y nunca debe presentarse como tal.

## Documentos vigentes

| Documento | Papel |
|---|---|
| **`docs/ESTADO.md`** (este) | Punto de entrada. Estado verificado y índice. |
| **`docs/superpowers/plans/2026-09-02-cierre-entrega-final.md`** | **Plan vigente.** 14 tareas hasta la entrega. Único plan a ejecutar. |
| `docs/superpowers/specs/2026-08-31-allianz-rag-design.md` | Especificación de diseño. Autoridad sobre alcance y contratos. |
| `docs/architecture/2026-08-31-api-y-experiencia-propuesta.md` | Anexo de la spec: API, estados y experiencia. |
| `docs/architecture/2026-08-31-stack-tecnologico-propuesto.md` | Anexo de la spec: stack y fronteras. |
| `docs/evaluation/2026-08-31-golden-set-y-metricas-rag.md` | Anexo de la spec: protocolo de golden y métricas. |
| `docs/evaluation/annotation-guide.md` | Taxonomía y flujo de anotación del golden. |
| `docs/evaluation/coverage-matrix.md` | Diseño de cobertura del golden. Sin casos admitidos todavía. |
| `docs/evaluation/golden-set-source-map.md` | Mapa de evidencias de los cinco siniestros. Verificado contra `pages.jsonl`. |
| `docs/rules/transcription-protocol.md` | Protocolo de doble transcripción de la matriz. |
| `docs/audit/2026-09-02-auditoria-integral-specs.md` | Auditoría contra la spec. **Cifras de tests desfasadas**; dictámenes cualitativos vigentes. |
| `docs/ingestion-baseline.md`, `docs/ingestion/parser-comparison.md` | Extracción baseline y comparativa de parsers. |
| `docs/operations/local-services.md` | Operación de los servicios locales. |
| `docs/enunciado/` | El enunciado original, tal cual se recibió. |
| `README.md`, `backend/README.md`, `frontend/README.md` | Puesta en marcha. |

## Documentos archivados

En `docs/archive/`. Se conservan como registro del proceso; **no se siguen**.

| Archivado | Por qué |
|---|---|
| `handoff-2026-09-01.md` | Describe un worktree y una rama (`feat/local-rag`) que ya no se usan, y trabajo sin commitear que se integró hace tiempo. |
| `deepwork-2026-09-02-cierre.md` | Estado de ejecución del Bloque A. Su contenido válido está en «Qué está hecho». Estaba fuera de Git (`.slim/` ignorado). |
| `deepwork-2026-09-02-handoff.md` | Afirma que T10 quedó revertido y pendiente en backend. **Es falso**: `73516e1` lo cerró. Estaba fuera de Git. |
| `plan-2026-08-31-allianz-rag-implementation.md` | Plan original de 21 tareas. Subsumido. |
| `plan-2026-09-02-remediacion-ux-observabilidad.md` | Plan de 15 tareas. Subsumido por el plan vigente, que mapea T1-T15 en su self-review. |
| `plan-2026-09-02-reorganizacion-repositorio.md` y su spec | Completado en `ce2d942`. |
| `e2e-report-2026-09-02.md` | Cita una rama inexistente, un HEAD 11 commits atrás y declara «LISTO PARA DEMO». Se regenerará desde resultados reales. |

## Estado verificado (2026-09-02)

### Gates

| Gate | Resultado medido |
|---|---|
| `make test-backend` | 331 passed, 1 skipped |
| `make lint-backend` | OK |
| `make check-frontend` | lint + typecheck + **60 tests** + build, OK |
| `make check-openapi` | **FALLA** — drift en `components` |

El único gate roto es OpenAPI: el commit `95800a2` añadió `trace_url` al sobre sin regenerar
`docs/api/openapi.json`. Se cierra en la Task 0 del plan vigente con
`uv run --project backend python backend/scripts/export_openapi.py`.

Nota conocida y benigna: `make check-backend` puede terminar con `Error 134` por un teardown de torch (`libc++abi`). No es un fallo de test.

Deuda registrada: `pyright --strict` reporta ~79 errores, excluidos del gate rápido y disponibles en `make typecheck-backend-strict`.

### Git

Rama `main`. `origin/main` está en `88d93cb`: **13 commits locales sin pushear**.

Sesión única a partir de `ccefd4f`: no hay otros agentes trabajando en el repositorio. Los commits
`95800a2`, `df71fbe` y `bb6c1a5` proceden de la sesión anterior y ya están incorporados a este
estado.

### Servicios

Compose `allianz-rag` sobre contexto `colima-allianz`: langfuse, langfuse-worker, clickhouse, postgres, redis, qdrant, minio, todos arriba. Backend responde `ready` en `:8000`. Qdrant tiene 4 colecciones; alias `allianz-manual-active` → `allianz-6e44144e9dde-98978fb804a6`.

### Qué está hecho

- **Ingestión**: contrato de publicación unificado; pypdf y Docling publican `original.pdf`. CLI `compare-parsers`. Páginas en blanco preservadas.
- **Perfiles e índices**: `IndexSignature` con 13 campos; CLI `index-rollback` y `list-index-versions`; `rollback_alias` verifica firma antes de mover el alias.
- **Recuperación**: densa + BM25 español + RRF nativo de Qdrant, intercambiables por configuración.
- **Workflows**: grafo documental (`retrieve → generate → validate`) y grafo de siniestros (`extract_facts → retrieve_criteria → apply_rules → explain → validate`). La extracción del LLM no puede sobrescribir el resultado determinista.
- **Reglas de aplicabilidad**: `domain/rules/applicability.py` implementa la puerta de dos vehículos, colisión directa, tercero identificado y colisión en cadena, con evidencia obligatoria. Verificado.
- **API**: nueve de las diez capacidades de la spec, con sobre común tipado, JSON y SSE. Los eventos llevan `event_id` y `timestamp`, y `dispatch` sólo se emite en modo `auto` (`73516e1`).
- **Frameworks de calidad**: CLI `golden validate/freeze/publish`, CLI `rules validate/compare-transcriptions`, schemas de matriz y ruleset con attestation obligatoria, validación de releases que rechaza `technical_fixture` por defecto.
- **Frontend**: React 19 + Vite, chat con tool calls, visor PDF, 60 tests unitarios, build limpio.
- **Historial real** (`df71fbe`): `lib/thread-store.ts` persiste hilos versionados en localStorage
  (`cicos.threads.v1`) con tolerancia a datos corruptos, cuota y sandbox. Cada hilo lleva un
  `session_id` estable. Sustituye a los hilos falsos. *(El docstring de `thread-sidebar.tsx:18`
  todavía dice «mock (5 hardcoded)»: es un comentario obsoleto, no el comportamiento.)*
- **Visor PDF** (`bb6c1a5`): cierre único y fallback explícito a página cuando no hay región
  verificada.

### Qué falta — los agujeros reales

Ordenados por impacto sobre la entrega.

1. **Los dos entregables documentales del enunciado no existen**: la presentación y el documento de arquitectura. El enunciado los exige explícitamente. → Tasks 11 y 12 del plan.
2. **`data/rules/` sólo tiene los schemas.** No existen `cide-matrix.v1.json` ni `ruleset.v1.json`, así que el flujo de siniestros nunca sale de `undetermined`. → Tasks 1, 2, 3.
3. **`data/evaluation/golden/` está vacío** (sólo `releases/`). Sin golden no hay comparativa de recuperación, ni métricas de router, ni holdout. → Tasks 4, 5.
4. **`data/extractions/` sólo contiene `pypdf-6.16.2`.** Sin la publicación Docling no hay bounding boxes y el visor no puede resaltar región. → Task 10.
5. **`session_id` existe en el frontend pero no en el backend.** `thread-store.ts` ya asigna uno estable por hilo (`df71fbe`), pero `backend/src` **no tiene ninguna ocurrencia** de `session_id`: no lo recibe ni lo propaga a Langfuse, así que las conversaciones siguen sin agruparse. Es media integración. → Task 8.
6. **El frontend fabrica duraciones.** El backend ya envía `timestamp` por evento; `frontend/src/lib/thread-state.ts` lo ignora y escribe `durationMs: 0` a mano en las líneas 505 y 516. → Task 10.
7. **Falta `GET /api/v1/demo/cases`**, la única capacidad HTTP de la spec sin implementar. → Task 13.
8. **El snapshot de OpenAPI está desincronizado** respecto al código. → Task 0.

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

1. Adjudicar las divergencias entre las dos transcripciones de la matriz y firmar la attestation. (Task 1, Step 9)
2. Validar el catálogo de las 18 circunstancias de la D.A.A. (Task 2, Step 7)
3. Revisar la anotación de los cinco siniestros antes de marcarlos `adjudicated`. (Task 4, Step 3)
