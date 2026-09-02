# Entrevista de Siniestros Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pedir sólo hechos materiales de un siniestro hasta poder aplicar una regla revisada, y no emitir una conclusión prematura.

**Architecture:** Un adaptador LLM produce hechos y un `InterviewPlan` tipado. El grafo LangGraph persiste ese plan y las respuestas en el `thread_id`, interrumpe exclusivamente para preguntas activas y ejecuta las reglas sólo tras `ready`. Los estados terminales de contradicción, falta de cobertura y límite de entrevista viajan hasta la API y el frontend.

**Tech Stack:** Python, Pydantic, LangGraph `interrupt`/`Command`, FastAPI/SSE, React/TypeScript, pytest, Vitest.

**Spec:** `docs/superpowers/specs/2026-09-02-entrevista-siniestros-design.md`

## Global Constraints

- El LLM puede decidir hechos faltantes y redactar preguntas, nunca atribuir culpa por sí solo.
- Toda decisión de culpa requiere una regla revisada coincidente y evidencia del manual.
- Nunca mostrar A0--A17 como requisito genérico; sólo una pregunta comprensible y material.
- Máximo tres rondas, tres preguntas por ronda, y parada inmediata si no hay progreso.
- Mantener `MemorySaver` sólo para local y preservar API explícita y automática.

### Task 1: Contrato tipado de entrevista

**Files:**
- Modify: `backend/src/application/models/claim.py`
- Modify: `backend/src/infrastructure/adapters/outbound/language_model/openai_claim_fact_extractor.py`
- Test: `backend/tests/test_openai_claim_fact_extractor.py`

- [ ] Añadir `InterviewQuestion` e `InterviewPlan` inmutables y validar IDs, estado y límite.
- [ ] Extender la salida estructurada del extractor con el plan; probar que se mapea y que el prompt prohíbe preguntas ya respondidas.
- [ ] Ejecutar el test del extractor y confirmar el fallo/paso de contrato.

### Task 2: Estado y rutas de LangGraph

**Files:**
- Modify: `backend/src/infrastructure/adapters/outbound/claim_workflow/langgraph_workflow.py`
- Modify: `backend/src/application/services/claim_analysis.py`
- Test: `backend/tests/test_claim_workflow.py`

- [ ] Guardar plan, rondas y respuestas; enrutar `ask` a un único interrupt JSON.
- [ ] Unir respuestas por ID, rechazar repeticiones y terminar por límite/no progreso.
- [ ] Bloquear evaluación hasta `ready`; distinguir contradicción y cobertura insuficiente de datos faltantes.
- [ ] Probar semáforo, respuesta parcial, no progreso y transición final sin recursión.

### Task 3: Reglas y hechos de los cinco casos

**Files:**
- Modify: `data/rules/ruleset.v1.json`
- Modify: `backend/src/infrastructure/adapters/outbound/language_model/openai_claim_fact_extractor.py`
- Modify: `backend/tests/test_ruleset_evaluation.py`
- Test: `backend/tests/test_claim_scenarios.py`

- [ ] Añadir al vocabulario los hechos de semáforos, versiones, identificación y maniobras de las reglas revisadas.
- [ ] Hacer evaluables únicamente las condiciones cuya transcripción y evidencia estén firmadas.
- [ ] Añadir los cinco escenarios y variantes incompletas como pruebas de aceptación.

### Task 4: API y experiencia de entrevista

**Files:**
- Modify: `backend/src/infrastructure/adapters/inbound/api/schemas/envelope.py`
- Modify: `frontend/src/api/queries.ts`
- Modify: `frontend/src/components/thread/clarification-panel.tsx`
- Modify: `frontend/src/lib/claim-format.ts`
- Test: `backend/tests/test_envelope_api.py`, `frontend/tests/unit/clarification-panel.test.tsx`

- [ ] Exponer preguntas tipadas, opciones, motivo y estado terminal mediante el envelope.
- [ ] Renderizar selectores para opciones, texto libre y “No lo sé”; enviar pares `question_id`/respuesta.
- [ ] Sustituir el titular genérico de indeterminación por mensajes específicos de contradicción, cobertura o entrevista agotada.

### Task 5: Verificación completa

**Files:**
- Modify: `docs/ESTADO.md`
- Test: backend y frontend completos.

- [ ] Ejecutar pytest, typecheck, build y OpenAPI check.
- [ ] Repetir visualmente: semáforos, alcance, cambio de carril, cinco vehículos, alcohol/lesiones, fuera de alcance e iteraciones parciales.
- [ ] Documentar límites del manual de 2004, `MemorySaver` local y cobertura de reglas.
- [ ] Commit y publicar los cambios en `main`.
