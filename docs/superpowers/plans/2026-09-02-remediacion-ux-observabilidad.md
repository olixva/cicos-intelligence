# Cierre integral del asistente Allianz — Plan de implementación

> **For the implementing agent:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Apply superpowers:test-driven-development for every behavior change and superpowers:verification-before-completion before each phase gate.

**Goal:** Convertir la primera demo en una entrega reproducible y demostrablemente correcta contra la especificación original, incluyendo ingestión, reglas, golden, experimentos, observabilidad, UX y pruebas reales.

**Architecture:** Mantener los límites hexagonales actuales. Hacer que los artefactos evaluables (publicaciones, perfiles, golden, matriz, runs y reportes) sean versionados e inmutables; que backend sea la única fuente de verdad de eventos/telemetría; y que frontend solo represente el contrato recibido.

**Tech Stack:** Python 3.14, FastAPI, LangGraph, Qdrant, Langfuse, Docling, OpenAI SDK, Ragas, React 19, TypeScript, Vite, Vitest y Playwright.

## Global Constraints

- No implementar decisiones CIDE/ASCIDE desde una tabla extraída automáticamente sin dos revisiones humanas independientes.
- No usar el holdout durante desarrollo o selección.
- No publicar métricas sin versionar dataset, perfil, prompt, modelos, commit y hashes de fuentes.
- Cada tarea comienza con test rojo o validador que falle y termina con evidencia ejecutada.
- No corregir retrospectivamente `docs/e2e-report.md`: regenerarlo desde resultados reales.
- Preservar cambios existentes del usuario; trabajar en rama/worktree aislado.

### Task 1: Restaurar un baseline reproducible y gates de calidad

**Files:** Modify `Makefile`, `backend/pyproject.toml`, `frontend/package.json`; create CI si procede; modify `README.md`.

1. Añadir comandos únicos para format-check, lint, typecheck, unit, integration, E2E y OpenAPI.
2. Corregir los 25 archivos detectados por `ruff format` sin cambios de comportamiento.
3. Reparar el locator ambiguo en `frontend/tests/e2e/smoke.spec.ts` y demostrar 2/2 verdes.
4. Resolver el bloqueo de dependencias pnpm de forma reproducible, sin desactivar controles globalmente.
5. Liberar espacio de `colima-allianz` solo con autorización; después construir ambos Dockerfiles desde cero.
6. Gate: backend tests, frontend tests/build/lint/types, E2E, OpenAPI y Docker pasan desde checkout limpio.

### Task 2: Publicaciones de ingestión inmutables y comparables

**Files:** Modify `backend/src/application/use_cases/ingest_document_use_case.py`, parsers y repositorio filesystem; create `backend/tests/test_ingestion_publication_contract.py`; modify `docs/ingestion/parser-comparison.md`.

1. Definir un único contrato de publicación para pypdf y Docling: fuente, hash, parser/config, páginas, assets, diagnostics y manifest.
2. Escribir tests que fallen por la diferencia actual de `original.pdf` y por assets ausentes.
3. Preservar una publicación Docling completa y verificable o crear un comando reproducible de materialización.
4. Añadir comparación automática de cobertura textual, tablas, imágenes, warnings, tamaño y tiempo.
5. Gate: reconstruir ambas publicaciones del PDF original y validar hashes/manifests sin pasos manuales.

### Task 3: Completar perfiles y promoción de índices

**Files:** Modify `backend/src/infrastructure/config/profiles.py`, perfiles, `index_builder.py`, `bootstrap.py`; add profile and retrieval integration tests.

1. Extender la identidad con parser, chunker, embedding, dense/sparse/hybrid, fusion, reranker, vision, ruleset, generator y prompt versions.
2. Rechazar índices incompatibles mediante signature completa.
3. Crear comandos de build/promote/rollback del alias de Qdrant.
4. Impedir que la demo apunte silenciosamente a baseline cuando el perfil exige Docling.
5. Gate: índices dense/BM25/hybrid construidos desde cero y alias promovido solo tras validación.

### Task 4: Construir y revisar el golden set y el dataset sintético

**Files:** Create `data/evaluation/golden/*.jsonl`, releases y `docs/evaluation/annotation-guide.md`; modify golden validation and CLI; add `backend/tests/test_golden_cli.py`.

1. Fijar taxonomía: documental, siniestro, router, ambiguo, no respondible, tablas/imagen, edge/adversarial.
2. Generar candidatos sintéticos únicamente desde evidencias identificadas; marcar provenance y generator.
3. Crear guía de anotación, doble revisión y adjudicación para evidencia, respuesta, decisión y abstención.
4. Implementar `allianz golden validate`, `review-status` y `freeze` con protección train/dev/holdout.
5. Publicar la release congelada en Langfuse Datasets con metadata versionada.
6. Gate: todos los casos tienen evidencia válida, revisión requerida y cero contaminación entre particiones.

### Task 5: Transcribir y validar la matriz y el corpus de reglas

**Files:** Create `data/rules/cide-matrix.v1.json`, `data/rules/ruleset.v1.json` y attestations; modify `backend/src/domain/rules/cide_matrix.py`, applicability rules and tests.

1. Definir schema para filas, columnas, códigos, orientación, simetría, notas y source evidence.
2. Realizar dos transcripciones independientes de las páginas relevantes.
3. Compararlas automáticamente y resolver divergencias mirando las imágenes originales.
4. Convertir condiciones CIDE/ASCIDE/CICOS en reglas versionadas, trazables a página/región.
5. Probar las 18×18 combinaciones, reversos, desconocidos, contradicciones y notas al pie.
6. Gate: attestation humana y totalidad verificada antes de permitir decisiones distintas de `undetermined`.

### Task 6: Terminar el flujo de siniestros

**Files:** Modify claim models/use case/workflow, fact extractor and API schemas; add scenario and golden integration tests.

1. Especificar hechos mínimos, clarificaciones, contradicciones y abstención.
2. Separar extracción atribuible, aplicabilidad, convenio, maniobras, lookup, decisión y explicación.
3. Emitir `rules_evaluated` reales con inputs, resultado y evidencia; nunca placeholders.
4. Generar explicación por bloques con condiciones, faltantes y citas.
5. Cubrir colisión directa/no directa, >2 vehículos, estacionados, versiones contradictorias, maniobra desconocida y fuera de convenio.
6. Gate: decisión y abstención alcanzan umbrales acordados en dev; holdout sigue sellado.

### Task 7: Evaluar y reparar consulta documental y recuperación

**Files:** Modify retriever/workflow/evaluators; create experiment runner CLI and report generator.

1. Ejecutar pypdf/Docling × fixed/section × dense/BM25/hybrid.
2. Añadir context expansion, reranking y visión como flags medibles, no hardcodes.
3. Implementar citation semantic correctness, context recall/precision, faithfulness, abstention y critical-error rate.
4. Registrar latencia p50/p95 y coste por etapa/configuración.
5. Seleccionar configuración con criterios predeclarados y documentar descartes.
6. Gate: informe reproducible identifica ganador y limita visión/rerank a donde aportan valor.

### Task 8: Evaluar y reparar el router automático

**Files:** Modify routing prompt/model/workflow; add router dataset and evaluator tests.

1. Crear conjunto balanceado question/claim/clarification con lenguaje realista y ambiguo.
2. Medir confusion matrix, macro-F1, precisión/recall por clase y error crítico.
3. Corregir el relato de accidente reproducido que se clasifica como pregunta.
4. Definir umbral de confianza y clarificación segura.
5. Gate: auto cumple thresholds; modos explícitos omiten clasificación backend y frontend.

### Task 9: Hacer Langfuse auditable de extremo a extremo

**Files:** Modify workflows/bootstrap/API metadata and tests; update operations docs.

1. Crear una única root trace por request y spans hijos coherentes.
2. Propagar `session_id` estable por conversación y `user_id` pseudónimo solo si procede.
3. Registrar profile, release, prompts, modelos, latencias, costes, input/output saneados y errores.
4. Obtener enlace con `get_trace_url`; no concatenar `/trace/{id}`.
5. Publicar scores de evaluadores y verificar Sessions/Experiments/Scores en UI.
6. Gate: desde un chat se abre su traza y desde Langfuse se reconstruye la conversación.

### Task 10: Convertir SSE en la fuente de verdad de estados y tiempos

**Files:** Modify API event schemas/routes/workflows, OpenAPI/types, streaming client and tool cards.

1. Diseñar eventos con event_id, request_id, timestamps y duración real.
2. Crear contract tests que fallen si se emite una etapa omitida o una duración inventada.
3. Eliminar timers simulados del frontend.
4. Soportar reconexión/idempotencia o declarar claramente el fallo no recuperable.
5. Gate: question y claim no muestran clasificación; auto sí; cada duración coincide con backend.

### Task 11: Historial de conversaciones real

**Files:** Modify `frontend/src/lib/thread-state.ts`, `storage.ts`, sidebar/App; expand unit and E2E tests.

1. Sustituir fixtures por threads reales con id, título, timestamps, mode y session_id.
2. Persistir, listar, seleccionar, recargar, renombrar y eliminar.
3. Mantener mensajes/resultados/citas al cambiar de hilo y recargar.
4. Probar hilo vacío, streaming activo, error, dos pestañas y storage corrupto.
5. Gate: cada entrada abre el chat correcto y su session_id coincide con Langfuse.

### Task 12: Corregir visor de evidencia y accesibilidad

**Files:** Modify PDF overlay, citation chip, evidence schemas/repository and styles; add unit/E2E visual tests.

1. Dejar un único cierre con foco, Escape y retorno de foco correctos.
2. Propagar bounding boxes desde Docling a chunks, resultados y API.
3. Resaltar región exacta; sin región, mostrar fallback explícito a página.
4. Sustituir BorderBeam azul por feedback sobrio compatible con reduced-motion.
5. Probar múltiples citas, página inexistente, hash incorrecto, zoom, teclado y móvil.
6. Gate: cada cita abre página/región correctas y controles accesibles.

### Task 13: Rediseñar empty state y pulir UX

**Files:** Modify empty state, globals/tokens and responsive tests/screenshots.

1. Rehacer sugerencias: centrado, ancho, borde y jerarquía visual.
2. Revisar responsive, light/dark, reduced motion, loading, empty, error y offline.
3. No presentar `undetermined` como éxito.
4. Gate: revisión visual móvil/tablet/desktop y snapshots aprobados.

### Task 14: Suite integral real y edge cases

**Files:** Expand `frontend/tests/e2e/`; create live-contract/evaluation suites; generate `docs/e2e-report.md`.

1. Cubrir los tres modos, historial, clasificación, clarificación, reglas, citas, PDF, Langfuse, errores, retry y accesibilidad.
2. Separar smoke mockeado de live E2E contra servicios reales.
3. Probar API validation, SSE ordering, timeouts, Qdrant vacío/incompatible, Langfuse caído y proveedor fallando.
4. Verificar payload, persistencia, traza, scores y evidencia; no solo apariencia.
5. Gate: informe generado desde JUnit/JSON, sin cifras manuales.

### Task 15: Experimento final, holdout y paquete de entrega

**Files:** Create experiment manifest/results/report, docs, demo script and presentation.

1. Ejecutar train/dev con perfiles congelados y publicar en Langfuse.
2. Calibrar evaluadores automáticos contra muestra humana y fijar thresholds.
3. Abrir holdout una sola vez tras congelar código/config; registrar sin tuning oculto posterior.
4. Documentar limitaciones, privacidad, recuperación, costes y decisiones experimentales.
5. Crear demo determinista y presentación con trazas/evidencias reales.
6. Gate final: checkout limpio → servicios → ingestión/indexado → tests → evaluación → demo; todo identifica commit y hashes.

## Orden y asignación recomendada

- **Bloque A (secuencial, agente principal):** Tasks 1–5. Fija verdad, datos y reglas.
- **Bloque B (paralelizable tras A):** Tasks 6–8. Workflows y evaluación.
- **Bloque C (paralelizable tras contratos):** Tasks 9–13. Observabilidad y frontend.
- **Bloque D (secuencial):** Tasks 14–15. Verificación final y entrega.

No delegar Tasks 4, 5, 7, 8 ni el diseño de Task 9 sin revisión del agente principal. Sí delegar implementaciones mecánicas de Tasks 1, 11, 12 y 13 una vez cerrados sus contratos.
