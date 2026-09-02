> [!WARNING]
> **DOCUMENTO ARCHIVADO — NO SEGUIR.** Archivado el 2026-09-02.
> Estado de ejecución del Bloque A, escrito fuera de Git (`.slim/` está ignorado) e incorporado aquí para no perderlo. Sus recuentos de tests están desfasados (dice 292/322; hoy son 331).
>
> Fuente de verdad actual: [`docs/ESTADO.md`](../ESTADO.md).
> Plan vigente: [`docs/superpowers/plans/2026-09-02-cierre-entrega-final.md`](../superpowers/plans/2026-09-02-cierre-entrega-final.md).

# Deepwork — Cierre integral Allianz RAG (2026-09-02)

## Goal & scope

Ejecutar el plan de cierre integral definido en
`docs/superpowers/plans/2026-09-02-remediacion-ux-observabilidad.md`
sobre la rama `main` ya reorganizada (commit `88d93cb`).
El cierre debe demostrar la cadena completa:
fuente → ingestión → publicación → perfiles → índices → golden →
dataset sintético → reglas/matriz → workflows → experimentos →
evaluación → holdout → observabilidad → interfaz → E2E → demo.

## Estado de partida (línea base)

- Working tree limpio; rama `main` sincronizada con `origin/main`.
- Servicios Compose vivos: langfuse (3000), qdrant (6333),
  postgres/redis/clickhouse/minio.
- Backend disponible en `127.0.0.1:8000` (FastAPI).
- Documentación leída: spec `2026-08-31`, plan original,
  auditoría integral `2026-09-02`, plan de cierre, diseño de
  reorganización, READMEs raíz/backend/frontend.
- Tests backend: 292 pasan + 1 skipped (referencia).
- Tests frontend: 51 unitarios pasan.
- Build frontend: pasa.
- OpenAPI: sin drift.
- Imágenes Docker: backend ≈ 9.78 GB, frontend ≈ 847 MB (referencia).
- Colecciones Qdrant: cuatro (alias activo apunta a Docling).
- Langfuse: responde; datasets/experimentos/sessions vacíos.

## Deuda técnica conocida (no regresión)

- Ruff format: ≈ 25 archivos backend sin formatear.
- Pyright completo: ≈ 79 errores.
- E2E oficial: solo 2 casos, 1 falla por locator ambiguo.
- Imagen backend Torch/CUDA innecesaria para CPU.
- `docs/e2e-report.md` sobreafirma cobertura real.

## Plan de fases (alineado con Bloques A–D del plan)

Las fases reflejan dependencias reales y límites de entrega.
Cada fase termina con un commit pequeño + gate + revisión Oracle
antes de la siguiente. No se fragmentan tareas solo para reducir
alcance de revisión.

### Fase 1 — Bloque A (Tasks 1–5): verdad, datos, reglas
- T1 reproducible baseline + gates de calidad.
- T2 publicaciones de ingestión inmutables y comparables.
- T3 perfiles completos + promoción de índices.
- T4 golden + dataset sintético.
- T5 matriz 18×18 + reglas con doble transcripción.
- Owner: agente principal (no delegable).
- Razón del gate: las decisiones de verdad, datos y reglas deben
  estar cerradas antes de evaluar workflows o tocar UX.

### Fase 2 — Bloque B (Tasks 6–8): workflows y evaluación
- T6 flujo de siniestros hasta umbrales en dev.
- T7 evaluación comparativa retrieval/generación.
- T8 router automático con thresholds.
- Owner: agente principal para T6/T7/T8 (decisiones de modelo
  y umbrales requieren revisión humana).
- Razón del gate: el modo automático no debe corregir
  retrospectivamente la referencia, y la evaluación define la
  selección final.

### Fase 3 — Bloque C (Tasks 9–13): observabilidad y frontend
- T9 Langfuse auditable extremo a extremo (diseño agente
  principal, implementación mecánica delegable).
- T10 SSE = fuente de verdad de estados/tiempos.
- T11 historial real (delegable a fixer tras contrato).
- T12 visor de evidencia y accesibilidad (delegable a designer
  + fixer tras contrato).
- T13 rediseño de empty state y pulido UX (delegable a
  designer tras contrato).
- Razón del gate: la UX solo puede pulirse una vez que el
  backend publica eventos/telemetría verdaderos.

### Fase 4 — Bloque D (Tasks 14–15): verificación final y entrega
- T14 suite integral real + edge cases.
- T15 experimento final + holdout + paquete de entrega.
- Owner: agente principal; el holdout se abre una sola vez y
  requiere registro explícito.
- Razón del gate: certifica la entrega.

## Disciplina de revisión

- 1 revisión inicial Oracle por fase + máximo 2 re-revisiones
  por fase.
- Re-revisión solo cuando la remediación cambia la decisión o
  el riesgo revisado, o cuando la preocupación original no
  puede verificarse con evidencia focal.
- Tras agotar re-revisiones: registrar riesgo restante y
  pedir decisión humana (aceptar, cambiar alcance o autorizar
  revisión excepcional).

## Restricciones críticas (no negociables)

- No inventar métricas, trazas, tiempos, reglas o resultados.
- No usar la matriz hasta tener dos transcripciones
  independientes + revisión humana.
- No abrir el holdout durante desarrollo.
- No convertir tablas Docling en reglas automáticamente.
- Backend = única fuente de verdad de etapas, timestamps y
  duraciones.
- Cada artefacto experimental identifica commit, hashes,
  perfil, prompts y modelos.

## Estado de ejecución (se actualiza al cerrar cada tarea)

### Fase 1 — Bloque A (Tasks 1–5): verdad, datos, reglas

**T1 — Baseline reproducible + gates de calidad** ✅
- 25 archivos backend re-formateados con `ruff format` (sin cambios
  de comportamiento; 292 tests siguen pasando).
- Locator ambiguo de `frontend/tests/e2e/smoke.spec.ts` corregido
  (heading scoped al banner; radios al fieldset); 2/2 E2E verdes.
- `Makefile` reescrito con targets individuales: lint, format-check,
  typecheck, test, integration, e2e, openapi, check-all.
- Wrapper `npm exec --yes pnpm@9.12.0 --` propagado al
  `playwright.config.ts` (host sin pnpm en PATH).
- Builds Docker verificados para backend y frontend desde cero.
- Baseline registrado: `pyright --strict` reporta **79 errores** (53 si
  se limita a `src/`). Excluido del `check-backend` rápido; disponible
  vía `make typecheck-backend-strict` para una fase posterior.
- Commits: `fe3fc78`, `7c890d3`.
- Estado backend: 292 → 292 passing.

**T2 — Publicaciones de ingestión inmutables y comparables** ✅
- `PypdfDocumentParser` ahora publica `original.pdf` como
  `BinaryAsset`, igualando el contrato de Docling. La API `/manual/pdf`
  ya no requiere copia manual del PDF.
- Nuevo test `backend/tests/test_ingestion_publication_contract.py`
  (7 tests) blinda el contrato: original.pdf presente, manifest
  canónico, publication.json con root_sha256, idempotencia,
  preservación de páginas en blanco, identidad de parser explícita.
- Nuevo `backend/scripts/compare_parsers.py` calcula cobertura textual
  bidireccional, inventario de assets y diferencias de tipos de
  elementos.
- Nuevo subcomando CLI `allianz compare-parsers SOURCE --output DIR`.
- Commits: `9b52b5e`, `37ad4e2`.
- Estado backend: 292 → 299 → 300 passing.

**T3 — Perfiles completos + promoción de índices** ✅
- `RetrievalProfile` extendida con retrieval_mode, fusion, reranker,
  vision, ruleset, generator y prompt_versions; `identity()` los cubre
  todos para que un cambio en cualquier campo invalide la identidad
  del índice.
- `_ProfileDocument` (Pydantic) acepta los nuevos campos con defaults
  retrocompatibles; perfiles YAML existentes siguen cargando.
- Nuevos subcomandos CLI: `allianz index-rollback --collection NAME`
  para volver a una colección anterior (con verificación post-cambio)
  y `allianz list-index-versions` para enumerar todas las colecciones
  con su `index_signature` y el alias activo.
- Commits: `1290c1a`.
- Estado backend: 300 → 307 passing.

**T4 — Golden set + dataset sintético (estructura)** 🟡 parcial
- Guía de anotación (`docs/evaluation/annotation-guide.md`) cubre la
  taxonomía completa (documental, siniestro, router, tabla/imagen,
  edge/adversarial, out-of-scope), el esquema por caso, el flujo de
  revisión ciega y las reglas que el sistema NO puede usar para
  generar la referencia.
- Esquema versionado `1.0.0` ya existía (`golden_schema.py`,
  `release_validation.py`). Quedaba sin CLI.
- Nuevos subcomandos CLI: `allianz golden validate`,
  `allianz golden freeze --dataset NAME --release ID`,
  `allianz golden publish --release ID [--golden-root DIR]`. El freeze
  valida de nuevo, genera manifest con hashes y publica solo si
  ambos hashes recalculados coinciden.
- Fixture técnico (`data/evaluation/golden/development.jsonl`) y round-
  trip end-to-end verificado con release `v0-cli-fixture`.
- Tests `backend/tests/test_golden_cli.py` (5): happy path, evidencia
  faltante, review incompleto, doble freeze, publish con Langfuse
  stub.
- **Pendiente humano**: contenido real de los casos `interview_example`
  y `synthetic` con los 5 siniestros originales y familias de la
  matriz. La guía de anotación marca exactamente qué debe validar
  cada revisor antes de que el caso pase a `adjudicated`.
- Commit: `a57952b`.
- Estado backend: 307 → 312 passing.

**T5 — Matriz 18×18 + reglas (transcripción doble)** 🟡 parcial
- Dos JSON Schemas (`cide-matrix.schema.json`, `ruleset.schema.json`)
  con enumeración cerrada de outcomes, attestation de doble
  transcripción + verificación de página PDF, y firmado obligatorio.
- Nuevo módulo `domain.rules.artifact_validation` valida ambos
  artefactos: esquema, 324 celdas (matriz), evidencia presente en
  publicación, attestation con ≥2 transcripciones independientes y
  `pdf_page_checked`, `divergence_resolution` y `signed_by` no vacíos.
- Nuevo `compare_transcriptions` reporta divergencias entre dos JSON
  crudos sin tocarlos.
- Nuevos subcomandos CLI: `allianz rules validate --matrix FILE
  [--ruleset FILE] [--evidence-roots ...]` y `allianz rules
  compare-transcriptions LEFT RIGHT`.
- Documento `docs/rules/transcription-protocol.md` describe el flujo
  completo de doble transcripción ciega y adjudicación contra PDF.
- Tests `backend/tests/test_rules_artifact.py` (10): schema, celdas
  completas, attestation corta, evidencia desconocida, hash incorrecto,
  divergencias, hash determinista, artefacto ausente, pool desde
  publications.
- **Pendiente humano**: doble transcripción de las 324 celdas + notas
  al pie + contenido del ruleset. El protocolo prohíbe explícitamente
  la conversión automática de tablas Docling y exige attestation
  firmada antes de cualquier uso.
- Commit: `9fa1eb6`.
- Estado backend: 312 → 322 passing.

**Estado gates globales**:
- `make check-backend` (ruff + ruff-format + pytest): ✅
- `make check-frontend` (lint + typecheck + test + build): ✅
- `make check-openapi` (backend + frontend): ✅
- `make test-e2e` (Playwright smoke): ✅ 2/2
- Backend tests totales: 322 + 1 skipped (era 292 al inicio de Bloque A).
- Frontend tests: 51 + build OK.
- Imágenes Docker: backend + frontend construyen en limpio.
- Langfuse + Qdrant + OpenAI: servicios vivos; ninguna publicación
  nueva tocada por el trabajo de Bloque A.

**Pendiente humano antes de continuar a Bloque B**:
1. Aprobar el contenido del fixture técnico `fixture-machinery-1`
   (¿se mantiene como ejemplo técnico separado, o se elimina antes de
   la primera release real?).
2. Validar la primera remesa de casos reales del golden set con el
   flujo de la guía de anotación (annotation-guide.md).
3. Validar la primera versión de `cide-matrix.v1.json` y
   `ruleset.v1.json` tras la doble transcripción.
4. Confirmar que la fase 1 está cerrada antes de pasar a Fase 2
   (siniestros, retrieval, router).
