# Cierre verificado de la entrega Allianz — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar una demo local honesta, reproducible y alineada con el enunciado original, con sus dos entregables documentales.

**Architecture:** Se conserva el backend hexagonal y el frontend React. Este plan no reescribe el producto: corrige los fallos verificables del corte, completa los contratos mínimos que exige el enunciado y documenta explícitamente todo lo que no se ha medido. `docs/ESTADO.md` será el índice de estado; este archivo será el único plan activo.

**Tech Stack:** Python 3.14, FastAPI, LangGraph, Qdrant, Langfuse, React 19, TypeScript, Vite, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-08-31-allianz-rag-design.md`; requisitos originales en `docs/enunciado/GenAI_Interview_Instructions.docx`.

## Global Constraints

- El manual fuente es `data/raw/Manual-cide-ascide-y-cicos.pdf`, SHA-256 `b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344`, edición de noviembre de 2004; no es derecho vigente.
- No inventar métricas, tiempos, resultados experimentales, trazas ni cobertura de evaluación.
- No usar la matriz CIDE sin circunstancias D.A.A. A y B explícitas; las etiquetas D.A.A. proceden de un formulario externo al manual.
- La reserva/holdout no se abre ni se presenta como evaluada sin un golden revisado.
- Ningún secreto de `.env` u `ops/local.env` se imprime, versiona o incorpora al frontend.
- Backend es la fuente de verdad para etapas y duraciones que se muestren en UI.
- Cada cambio de comportamiento empieza por un test que falle y termina con la verificación indicada.

---

## Estado de partida comprobado el 2026-09-02

| Control | Resultado real |
| --- | --- |
| `make test-backend` | 398 passed, 1 skipped |
| `make format-check` | OK |
| `make lint-backend` | OK tras ordenar imports en `backend/tests/test_daa_circumstances.py` |
| `make typecheck-backend` | Falla: 100 errores de Pyright |
| `make check-frontend` | lint, tipos, 90 tests y build OK |
| `make check-openapi` | OK |
| `make test-e2e` | 2 passed |
| Prueba real UI | pregunta de alcoholemia contestada, p. 9 y visor PDF correctos |

### Task 1: Recuperar el gate de calidad declarado — completada el 2026-09-02

**Files:**
- Modify: `backend/tests/test_daa_circumstances.py:3-4`
- Verify: `Makefile` targets existentes

- [x] **Step 1: Reproducir el fallo.** `make lint-backend` confirmó `I001` en el bloque `json`/`Path`.
- [x] **Step 2: Corregir únicamente el orden de imports.** Se eliminó una línea vacía extra; ningún cambio funcional.
- [x] **Step 3: Ejecutar `make lint-backend && make format-check && make test-backend`.** Resultado: lint/formato OK; 398 passed, 1 skipped.
- [x] **Step 4: Ejecutar `make typecheck-backend`.** Sigue fallando con 100 errores; `docs/ESTADO.md` lo declara explícitamente.

### Task 2: Propagar la sesión de conversación hasta Langfuse

**Files:**
- Modify: `frontend/src/api/queries.ts`
- Modify: `frontend/src/routes/_index.tsx`
- Modify: schemas, rutas y workflows backend que reciben `EnvelopeRequest`
- Test: tests API/backend y `frontend/tests/unit/streaming-client.test.tsx`

**Interfaces:**
- Produces: `session_id: string | null` en cada petición de sobre y en la root trace correspondiente.

- [ ] **Step 1: Escribir pruebas fallidas** que comprueben que una petición con `session_id` llega a la ejecución y que modos explícitos conservan la sesión sin clasificar.
- [ ] **Step 2: Ejecutar sólo esas pruebas** y confirmar que fallan por la ausencia del campo.
- [ ] **Step 3: Añadir el campo al contrato OpenAPI y propagarlo desde el hilo activo al workflow/Langfuse.** No generar sesiones nuevas en backend.
- [ ] **Step 4: Regenerar OpenAPI y ejecutar pruebas unitarias, `make check-openapi` y una consulta UI.** Comprobar que la traza queda agrupada por sesión en Langfuse.

### Task 3: Casos de demo en alcance y endpoint público seguro

**Files:**
- Create: `data/evaluation/golden/development.jsonl`
- Modify: `backend/src/infrastructure/adapters/inbound/api/app.py`
- Create: `backend/src/infrastructure/adapters/inbound/api/routes/demo.py`
- Modify: `frontend/src/components/empty-state/empty-state.tsx`
- Test: `backend/tests/test_demo_api.py`, `frontend/tests/unit/empty-state.test.tsx`

**Interfaces:**
- Produces: `GET /api/v1/demo/cases`, que expone sólo `case_id`, `text`, `language` y `expected_intent` de casos development, sin referencias, etiquetas de salida ni reserva.

- [ ] **Step 1: Redactar cinco casos development: los cinco relatos del enunciado.** Marcar revisión humana pendiente cuando proceda; no llamarlos golden adjudicado.
- [ ] **Step 2: Escribir pruebas fallidas** de que el endpoint omite `expected_output`, no devuelve reserva y sólo emite entradas development permitidas.
- [ ] **Step 3: Implementar el cargador read-only y la ruta.** Fallar con error controlado si el fichero no contiene casos development válidos.
- [ ] **Step 4: Sustituir sugerencias hardcodeadas, incluido baremo 2025, por los casos expuestos.** No incluir contenido externo al manual.
- [ ] **Step 5: Ejecutar tests, OpenAPI, build y revisión visual de empty state.**

### Task 4: Evidencia, evaluación y límites demostrables

**Files:**
- Create: `data/evaluation/golden/documental.jsonl`
- Create: `docs/evaluation/resultados-dev.md`
- Modify: `docs/evaluation/coverage-matrix.md`
- Test: validadores golden existentes

- [ ] **Step 1: Crear candidatos documentales con evidencia física verificable del manual.** Mantenerlos en desarrollo y distinguir candidato de caso adjudicado.
- [ ] **Step 2: Solicitar/reunir revisión humana por caso antes de congelar una release.** Si no se produce, conservar el estado `pending_review` y no publicar métricas.
- [ ] **Step 3: Ejecutar `allianz golden validate` sólo sobre casos revisados.** No usar `technical_fixture` como dataset de entrega.
- [ ] **Step 4: Escribir resultados únicamente con denominador, hashes, perfil, modelo, fecha y comando ejecutado.** Si no hay resultados, documentar la ausencia y su impacto.

### Task 5: Dos entregables de la entrevista y ensayo

**Files:**
- Create: `docs/entrega/arquitectura.md`
- Create: `docs/entrega/presentacion.pptx`
- Create: `docs/entrega/guion-demo.md`
- Modify: `README.md`, `docs/ESTADO.md`

- [ ] **Step 1: Redactar arquitectura desde el código y las verificaciones del corte.** Incluir hexágono, dos workflows, ingesta, evidencia, límites, retos y deuda medida.
- [ ] **Step 2: Crear presentación de 30–45 minutos con capturas reales.** Incluir alcance, decisiones, cinco relatos, abstención, evaluación medida/pendiente, riesgos, hitos y plan de contingencia.
- [ ] **Step 3: Crear guion de demo reproducible.** Incluir arranque, cada entrada, salida esperada, fuente que se abre y contingencia por OpenAI/Qdrant/Langfuse.
- [ ] **Step 4: Renderizar e inspeccionar visualmente los dos artefactos.** Verificar que no hay afirmaciones sin evidencia.

### Task 6: Cierre verificable y documentación única

**Files:**
- Modify: `docs/ESTADO.md`
- Modify: `README.md`

- [ ] **Step 1: Actualizar `docs/ESTADO.md` tras cada tarea con comandos y resultados reales.**
- [x] **Step 2: Eliminar planes, handoffs e informes históricos que duplicaban o contradecían el estado.** Git conserva el historial; `docs/ESTADO.md` enlaza sólo las fuentes vigentes.
- [ ] **Step 3: Ejecutar `make check-all`, `make test-e2e`, `make doctor` y el ensayo visual.** Informar por separado cualquier fallo restante.

### Ampliación aprobada: modo administrador e ingesta por API

La especificación y el plan de esta ampliación viven en:

- `docs/superpowers/specs/2026-09-02-admin-ingestion-design.md`
- `docs/superpowers/plans/2026-09-02-admin-ingestion.md`

La operación normal de la demo ya no necesita el CLI para ingerir o indexar. El CLI técnico se conserva únicamente para mantenimiento, evaluación, validación y CI.
