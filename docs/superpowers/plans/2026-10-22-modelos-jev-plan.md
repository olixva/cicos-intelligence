# OpenAI Model and Jev Adoption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Actualizar los modelos OpenAI y activar Jev para router y guardarraíl sólo cuando comparaciones reproducibles confirmen que cumple las puertas de calidad y seguridad.

**Architecture:** Se corrigen primero la normalización y las métricas del runner para que los A/B no pierdan casos ni oculten denominadores. Después se actualizan los defaults de OpenAI, se valida su API real y se compara Jev por separado para router y guardarraíl; cada proveedor queda predeterminado sólo si supera su puerta.

**Tech Stack:** Python 3.14, Pydantic, httpx, FastAPI, Pytest, scripts de evaluación del repositorio, Responses API de OpenAI y System One de TypeSafe/Jev.

**Spec:** `docs/superpowers/specs/2026-10-22-modelos-jev-diseno.md`

## Global Constraints

- Respuesta documental: `gpt-6.1-sol`.
- Extracción: probar `gpt-6-luna`; conservarla sólo si no añade resoluciones injustificadas ni empeora materialmente las métricas adjudicadas; de lo contrario usar `gpt-6.1-sol`.
- Router OpenAI de referencia: `gpt-6-luna`; embeddings `text-embedding-3-small` de 1536 dimensiones, sin cambios.
- Jev sólo toma decisiones tipadas; no genera respuestas documentales ni sustituye la extracción completa de hechos en esta fase.
- El regex de guardarraíl se ejecuta antes de Jev; el guardarraíl Jev conserva su fallo abierto; baja confianza del router pide aclaración; el router Jev no hace fallback silencioso.
- Activar por separado router y guardarraíl Jev, sólo tras cumplir los criterios de la especificación.
- Usar golden y relatos sintéticos con TypeSafe. No enviar relatos reales con datos personales hasta revisar el acuerdo de tratamiento y retención.
- Las claves viven en variables de entorno y no se escriben en Git, logs, trazas ni artefactos versionados.
- Las métricas del juez Jev quedan marcadas como exploratorias hasta medir acuerdo con etiquetas humanas.
- Los IDs de modelos en corridas históricas no se reescriben; se actualizan defaults, instrucciones operativas y resultados nuevos.

## Mapa de archivos

- `backend/src/application/models/evaluation.py` y `backend/src/application/services/evaluation_normalization.py`: contrato normalizado que separa intención de ruta, tipo de resultado, necesidad de aclaración y error técnico.
- `backend/src/infrastructure/adapters/outbound/evaluation/evidence_evaluators.py` y `domain_evaluators.py`: agregados con denominadores cerrados y cobertura lógica de evidencia.
- `backend/scripts/run_baseline.py`: ejecución, persistencia por caso, reanudación y manifiesto suficiente para comparar corridas.
- `backend/src/bootstrap.py`, `query_workflow/langgraph_workflow.py`, `.env.example` y documentación: modelos predeterminados y variables operativas.
- `backend/src/infrastructure/adapters/outbound/decision_model/jev_client.py`, `jev_input_guard.py` y pruebas existentes: contrato remoto tipado y activación independiente de Jev.
- `backend/scripts/run_redteam.py`: metadatos de cada campaña para distinguir guardarraíl, thresholds y modelos.
- `docs/operacion.md`, `docs/evaluacion.md`, `docs/entrega/memoria.md` y `docs/entrega/validacion-pendiente.md`: procedimiento, resultados medidos y límites pendientes.

## Review Focus

- Una ejecución `auto` puede enrutar a `claim` y terminar pidiendo aclaración; el evaluador conserva `route_decision="claim"` y `needs_input=True` (Task 1).
- Un error técnico o métrica desconocida no invalida ni desaparece casos ya guardados; reanudar sólo repite casos incompletos o fallidos (Task 1).
- Un paquete de evidencia `all_of` incompleto falla, un paquete `any_of` completo basta y una cita ausente cuando es obligatoria puntúa cero (Task 2).
- Una respuesta Jev mal formada, de baja confianza o con error de proveedor no se convierte en una ruta inventada ni en un fallback invisible (Task 5).
- El guardarraíl no rechaza controles benignos por encima de la referencia y cualquier ataque exitoso bloquea su promoción (Task 6).

---

### Task 1: Normalizar resultados y hacer reanudables las corridas

**Files:**
- Create: `backend/src/application/models/evaluation.py`
- Create: `backend/src/application/services/evaluation_normalization.py`
- Create: `backend/tests/test_evaluation_normalization.py`
- Modify: `backend/scripts/run_baseline.py`

**Interfaces:**
- Produce `EvaluableTurn.from_envelope(response: Mapping[str, object], requested_mode: str) -> EvaluableTurn` y `EvaluableTurn.from_error(error: BaseException) -> EvaluableTurn`, con `route_decision: str | None`, `result_kind: str | None`, `needs_input: bool`, `terminal_status: str | None` y `technical_error: str | None`.
- `run_baseline.py` consume ese contrato; escribe un archivo por caso/modo de forma atómica y admite `--resume` sólo si el manifiesto de identidad (golden, modos, modelos y commit) coincide.

- [x] **Step 1: Escribir pruebas fallidas** `test_auto_claim_clarification_keeps_route_decision`, `test_http_error_is_preserved_as_technical_error`, `test_unknown_metric_does_not_abort_aggregation`, `test_resume_reuses_complete_records_and_retries_errors` y `test_case_json_is_atomically_replaced`. Incluir `auto → claim → clarification` con `route_decision="claim"` y `needs_input=True`.
- [x] **Step 2: Ejecutar `uv run --project backend pytest backend/tests/test_evaluation_normalization.py -q`** y confirmar fallo por interfaz ausente.
- [x] **Step 3: Implementar `EvaluableTurn` y `from_envelope`** en los dos módulos nuevos; derivar la decisión de ruta y el resultado final de campos separados del envelope.
- [x] **Step 4: Adaptar el runner** para guardar cada caso/modo mediante escritura temporal más rename, resumir sólo registros completos compatibles y volver a ejecutar registros con error; una métrica desconocida se registra por caso y no aborta `_aggregate`.
- [x] **Step 5: Ejecutar `uv run --project backend pytest backend/tests/test_evaluation_normalization.py backend/tests/test_evaluation.py -q`**; verificar que los casos ya persistidos sobreviven a una reanudación simulada.
- [x] **Step 6: Commit** `fix(eval): normalize outcomes and preserve partial runs` (`c8a10db`).

### Task 2: Corregir denominadores y medir evidencia AND/OR

**Files:**
- Modify: `backend/src/infrastructure/adapters/outbound/evaluation/domain_evaluators.py`
- Create: `backend/src/infrastructure/adapters/outbound/evaluation/evidence_evaluators.py`
- Modify: `backend/src/application/models/evaluation.py`
- Modify: `backend/scripts/run_baseline.py`
- Modify: `backend/tests/test_evaluation.py`

**Interfaces:**
- Produce `MetricAggregate(n_total: int, n_applicable: int, n_scored: int, n_missing: int, n_error: int, n_not_applicable: int, mean: float | None)`; cada agregado cumple `n_total = n_scored + n_missing + n_error + n_not_applicable` y `n_applicable = n_total - n_not_applicable`.
- Produce `citation_id_validity(*, cited: Collection[str], valid_pool: Collection[str], citations_required: bool = False) -> float | None`, `evidence_bundle_coverage(*, cited: Collection[str], requirements: Sequence[EvidenceRequirement]) -> float | None`, `over_resolution_rate_against_reference(*, predicted_decisions: Sequence[str], expected_decisions: Sequence[str]) -> float | None` y `resolution_support_rate(*, result: Mapping[str, object]) -> float | None`.

- [x] **Step 1: Escribir pruebas fallidas** `test_all_of_bundle_requires_each_citation`, `test_any_of_accepts_one_complete_bundle`, `test_required_missing_citations_score_zero`, `test_metric_aggregate_counts_close_total` y `test_missing_and_error_are_not_scored`.
- [x] **Step 2: Ejecutar `uv run --project backend pytest backend/tests/test_evaluation.py -q`** y confirmar que los casos nuevos fallan.
- [x] **Step 3: Implementar `MetricAggregate` en `application/models/evaluation.py` y los evaluadores** separando validez de ID respecto al catálogo y cobertura de evidencia exigida por el golden; un requisito se cubre si algún bundle `any_of` incluye todos sus IDs `all_of`, y una cita obligatoria ausente puntúa 0.
- [x] **Step 4: Integrar los agregados al runner**; separar `over_resolution_rate_against_reference` de `resolution_support_rate`, que comprueba regla matched, actor y evidencia estructurados. Si el envelope aún no expone actor, registrar la medida como missing; no inferirlo del texto libre.
- [x] **Step 5: Recalcular los resultados históricos sólo desde sus archivos `per-case`**, guardando una salida nueva con `recomputed_from`; si los archivos originales no están disponibles, dejar el histórico marcado como no recalculable y no inventar agregados.
- [x] **Step 6: Ejecutar `uv run --project backend pytest backend/tests/test_evaluation.py backend/tests/test_evaluation_normalization.py -q`** y comprobar las identidades de denominadores.
- [x] **Step 7: Commit** `fix(eval): report honest denominators and evidence coverage` (`e98a106`).

### Task 3: Actualizar defaults OpenAI y documentar la configuración segura

**Files:**
- Modify: `.env.example`
- Modify: `backend/src/bootstrap.py`
- Modify: `backend/src/infrastructure/adapters/outbound/query_workflow/langgraph_workflow.py`
- Modify: `backend/src/application/services/routing.py`
- Modify: `backend/src/application/services/claim_heuristics.py`
- Create: `backend/tests/test_model_configuration.py`
- Modify: `backend/tests/test_routing.py`
- Modify: `docs/operacion.md`, `docs/evaluacion.md`, `docs/entrega/memoria.md`, `docs/entrega/validacion-pendiente.md`

**Interfaces:**
- Defaults: `OPENAI_ANSWER_MODEL=gpt-6.1-sol`, `OPENAI_CLAIM_EXTRACTION_MODEL=gpt-6.1-sol` hasta decidir Luna con datos, `ALLIANZ_ROUTER_MODEL=gpt-6-luna`.
- Se mantienen las variables y firmas de Responses API; `ALLIANZ_ROUTER_BACKEND` queda como opción separada.

- [x] **Step 1: Escribir pruebas fallidas `test_openai_model_defaults` y `test_openai_model_environment_overrides_defaults`** en `test_model_configuration.py`.
- [x] **Step 2: Ejecutar `uv run --project backend pytest backend/tests/test_model_configuration.py backend/tests/test_routing.py -q`** y confirmar fallo de los defaults.
- [x] **Step 3: Actualizar defaults y comentarios** en bootstrap, workflow, heurísticas y `.env.example`; no cambiar embeddings ni referencias históricas a modelos de corridas antiguas.
- [x] **Step 4: Actualizar documentación** para separar configuración propuesta, comprobaciones reales pendientes y resultados históricos; describir la selección segura Sol para extracción antes de aprobar Luna.
- [x] **Step 5: Ejecutar las pruebas focalizadas** y revisar con `rg -n 'gpt-5\\.6'` que sólo queden referencias identificadas como históricas o fixtures.
- [x] **Step 6: Commit** `feat(models): update OpenAI defaults to GPT-6` (`964590c`).

### Task 4: Validar OpenAI y comparar modelos de extracción

**Files:**
- Modify: `docs/evaluacion.md`
- Modify: `docs/entrega/memoria.md`
- Modify: `docs/entrega/validacion-pendiente.md`
- Artifacts (locales, ignorados): `data/evaluation/results/<fecha>-openai-sol/` y `data/evaluation/results/<fecha>-openai-luna/`

**Interfaces:**
- Usa `run_baseline.py` y el mismo golden adjudicado, mismo commit de código, perfil, concurrencia, índice y prompts; sólo cambia `OPENAI_CLAIM_EXTRACTION_MODEL` entre `gpt-6.1-sol` y `gpt-6-luna`.
- Cada corrida conserva manifiesto, resultados por caso, uso/coste disponible, errores y latencia.

- [x] **Step 1: Comprobar el catálogo y acceso real** a `gpt-6-luna` mediante `OPENAI_API_KEY` del entorno; lanzar humo sintético de pregunta y claim con salida estructurada. No se invocó Sol por instrucción expresa del usuario.
- [ ] **Step 2: Ejecutar el mismo golden completo con Sol y Luna** en dos procesos backend. Comparación de extracción pendiente: el usuario limitó las llamadas OpenAI de esta campaña a Luna.
- [ ] **Step 3: Comparar** errores de proveedor, campos de extracción, métricas de decisión, nuevas resoluciones injustificadas, tokens/coste y latencia con denominadores corregidos.
- [ ] **Step 4: Mantener Luna sólo si no produce nuevas resoluciones injustificadas y no empeora materialmente métricas de seguridad adjudicadas**; de lo contrario conservar Sol. Registrar el criterio y la evidencia en memoria y validación pendiente.
- [x] **Step 5: Commit** `docs(eval): record GPT-6 extraction comparison` (`3f59476`); el commit registra que la comparación Sol/Luna no se ejecutó y deja Sol como default de extracción.

### Task 5: Verificar Jev y promover el router sólo si supera el A/B

**Files:**
- Modify: `backend/src/infrastructure/adapters/outbound/decision_model/jev_client.py` si el contrato remoto real requiere ajuste
- Modify: `backend/tests/test_decision_model.py`
- Modify: `backend/scripts/run_baseline.py`
- Modify: `backend/scripts/run_redteam.py` sólo para completar metadatos comunes de proveedor/configuración
- Modify: `.env.example`, `backend/src/bootstrap.py`, `docs/operacion.md`, `docs/evaluacion.md`, `docs/entrega/memoria.md`, `docs/entrega/validacion-pendiente.md`

**Interfaces:**
- `JevDecisionModel.decide(state, questions) -> DecisionResult` valida una respuesta para cada clave, tipo correcto y probabilidades en `[0, 1]`; `DecisionResult` conserva modelo y uso.
- El manifiesto identifica proveedor/modelo/umbral del router y el resultado se compara con el router OpenAI sobre los mismos casos.

- [x] **Step 1: Añadir pruebas fallidas** `test_response_requires_every_asked_question`, `test_choice_probability_out_of_range_is_rejected` y `test_provider_error_body_is_not_exposed`; verificar respuesta ausente, tipo incorrecto y cuerpo remoto no expuesto.
- [x] **Step 2: Ejecutar `uv run --project backend pytest backend/tests/test_decision_model.py -q`** y confirmar los casos nuevos.
- [x] **Step 3: Hacer una llamada sintética real** con preguntas `noul` y `choice`; respuesta, probabilidades, modelo y usage verificados. Los tests unitarios cubren timeout/HTTP y ausencia de clave.
- [x] **Step 4: Ejecutar A/B del golden** con OpenAI Luna y Jev; se registraron exactitud end-to-end, matrices, errores, duración, tokens y coste estimado. El barrido inicial probó `0.4`, `0.6`, `0.8`; luego se repitió el A/B de `0.4` y OpenAI con manifiestos y `per-case` nativos.
- [x] **Step 5: Promover `jev` como router predeterminado**; en la repetición Jev `0.4` obtuvo 97/110 frente a OpenAI Luna 94/110, contando errores y rutas ausentes como fallos del flujo `auto`. OpenAI queda seleccionable; no hay fallback silencioso.
- [x] **Step 6: Ejecutar tests focalizados de cliente/bootstrap y guardar resultados fuera de Git**; los manifiestos retenidos identifican proveedor, modelo y umbral.
- [x] **Step 7: Commit** `feat(models): promote validated Jev defaults` (`75da632`).

### Task 6: Validar guardarraíl Jev con red-team y decidir su default

**Files:**
- Modify: `backend/tests/test_decision_model.py`
- Modify: `backend/tests/test_redteam.py`
- Modify: `backend/scripts/run_redteam.py`
- Modify: `.env.example`, `backend/src/bootstrap.py`, `docs/operacion.md`, `docs/evaluacion.md`, `docs/entrega/memoria.md`, `docs/entrega/validacion-pendiente.md`
- Artifacts (locales, ignorados): `data/evaluation/results/<fecha>-redteam-off/` y `data/evaluation/results/<fecha>-redteam-jev/`

**Interfaces:**
- `ALLIANZ_INPUT_GUARD=off|jev` controla el guardarraíl independientemente del router; el manifiesto guarda backend, threshold de inyección y threshold off-topic.
- La promoción exige cero ataques exitosos y `over_refusal_rate` Jev no mayor que la referencia `off`.

- [x] **Step 1: Añadir `test_redteam_manifest_records_guard_backend_and_thresholds` y `test_regex_guard_runs_before_jev_guard`**; conservar `test_guard_fails_open_when_the_service_is_down` como prueba de fallo abierto.
- [x] **Step 2: Ejecutar `uv run --project backend pytest backend/tests/test_decision_model.py backend/tests/test_redteam.py -q`**; las pruebas focalizadas pasan.
- [x] **Step 3: Ejecutar la suite red-team completa** con guard `off` y `jev`, sobre el mismo backend/configuración; no hubo ataques fallidos, y se inspeccionaron controles benignos.
- [x] **Step 4: Activar `jev` por defecto**; el éxito de ataque fue 0 y el sobre-rechazo igualó la referencia `off`.
- [x] **Step 5: Mantener el juez Jev opt-in y marcar sus scores como exploratorios** hasta medir acuerdo con etiquetas humanas.
- [x] **Step 6: Registrar manifiestos, resultados, umbrales y límites** sin relatos personales ni secretos.
- [x] **Step 7: Commit** `feat(models): promote validated Jev defaults` (`75da632`).

### Task 7: Cerrar trazabilidad y ejecutar puertas de entrega

**Files:**
- Modify: `docs/operacion.md`
- Modify: `docs/evaluacion.md`
- Modify: `docs/entrega/memoria.md`
- Modify: `docs/entrega/validacion-pendiente.md`
- Review: `.env.example`, manifiestos locales, `git status` y referencias a secretos

- [x] **Step 1: Consolidar en memoria** fecha, IDs, mediciones de tokens/duración, denominadores, estimación de coste y límites; distinguir los resultados parciales.
- [x] **Step 2: Confirmar** que los jueces Jev no calibrados siguen etiquetados como exploratorios y que no queda como pendiente ninguna comprobación que sí se ejecutó.
- [x] **Step 3: Ejecutar `make check-all` y `make test-e2e`**; resolver fallos de esta rama y guardar salida reproducible.
- [x] **Step 4: Revisar `git diff --check`, búsqueda de claves, modelo de embedding intacto y referencias antiguas sólo históricas; verificar que resultados y secretos no se hayan añadido a Git.
- [x] **Step 5: Commit** documentación y cierre local de Jev/modelos.

**Cierre de revisión independiente:** la métrica ahora se denomina
`router_end_to_end_accuracy_all_labeled` y declara que incluye dispatch y
disponibilidad de respuesta/extracción, no sólo clasificación. `/health/config`
expone modelos y umbrales sin credenciales; ambos runners cotejan ese snapshot
antes de enviar casos y abortan ante divergencia. El endpoint confirma el
commit y la huella del árbol de trabajo del servidor, además de la firma real
de la colección detrás del alias activo de Qdrant; los runners cotejan el hash
del documento firmado con el esperado. El manifiesto red-team guarda commit,
hash de casos, hash/páginas del manual y concurrencia. Los A/B finales
volvieron a ejecutarse en commit `75da632`, con 110 archivos por caso nativos;
ambas pasadas parciales se reanudaron y su limitación de duración del manifiesto
se documenta. La duración acumulada aparece en el manifiesto, el resumen y la
consola y tiene prueba de regresión. La
muestra benigna sigue siendo sólo n=3 y el umbral requiere un holdout.

## Self-review del plan

- **Cobertura de especificación:** normalización/denominadores preceden A/B; respuestas OpenAI, extracción comparativa, cliente Jev, router, guardarraíl, calibración del juez y memoria tienen tareas y gates explícitos.
- **Consistencia de interfaces:** las métricas usan campos definidos en Task 2 y el runner registra los mismos proveedores/modelos/thresholds comparados en Tasks 4–6.
- **Seguridad de datos:** validación remota TypeSafe usa datos sintéticos; el plan no incorpora credenciales a comandos versionados ni artefactos Git.
- **Alcance:** esta fase cierra modelos y Jev; las correcciones funcionales restantes de la auditoría entregada siguen como fase posterior, tal como aprobó la especificación.
