# Estado del proyecto — punto de entrada único

**Última verificación independiente: 2026-09-02 (sesión de noche).** Este documento es el índice único de estado. Las afirmaciones de ejecución se apoyan en los comandos del corte; cualquier documento que las contradiga queda superado. Verificado directamente contra el código y los artefactos, no contra documentación previa: una sesión anterior dejó borrados sin commitear `docs/entrega/`, las capturas y dos planes/specs de ingesta admin, sin actualizar por completo este índice en consecuencia. Esta revisión corrige esas referencias muertas.

## Qué es este proyecto

Prueba técnica de Allianz (`GenAI_Interview_Instructions.docx`, SHA-256 `8561213339f76c7bd8a6c56fa0c91323c6d838ae0e9d0f30a12d8e3f775a4957`): un sistema RAG sobre el manual CIDE/ASCIDE/CICOS que responde preguntas del manual y analiza relatos de accidentes.

Fuente documental: `data/raw/Manual-cide-ascide-y-cicos.pdf`, 111 páginas, SHA-256 `b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344`, edición de **noviembre de 2004**. No es derecho vigente y nunca debe presentarse como tal.

## Documentos vigentes

| Documento | Papel |
|---|---|
| **`docs/ESTADO.md`** (este) | Punto de entrada. Estado verificado y índice. |
| `docs/superpowers/specs/2026-08-31-allianz-rag-design.md` | Especificación de diseño. Autoridad sobre alcance y contratos. |
| `docs/architecture/2026-08-31-api-y-experiencia-propuesta.md` | Anexo de la spec: API, estados y experiencia. |
| `docs/architecture/2026-08-31-stack-tecnologico-propuesto.md` | Anexo de la spec: stack y fronteras. |
| `docs/evaluation/2026-08-31-golden-set-y-metricas-rag.md` | Anexo de la spec: protocolo de golden y métricas. |
| `docs/evaluation/annotation-guide.md` | Taxonomía y flujo de anotación del golden. |
| `docs/evaluation/coverage-matrix.md` | Diseño de cobertura del golden. Hoy hay **110 casos admitidos** en `development.jsonl` (los 5 accidentes del enunciado + 5 variantes ES de releases anteriores + 100 sintéticos), congelados como release `synthetic-expansion-110-2026-09-03`. |
| `docs/evaluation/golden-set-source-map.md` | Mapa de evidencias de los cinco siniestros. Verificado contra `pages.jsonl`. |
| `docs/rules/transcription-protocol.md` | Protocolo de doble transcripción de la matriz. |
| `docs/ingestion-baseline.md`, `docs/ingestion/parser-comparison.md` | Extracción baseline y comparativa de parsers. |
| `docs/operations/local-services.md` | Operación de los servicios locales. |
| `docs/enunciado/GenAI_Interview_Instructions.docx` | Enunciado original, tal como se recibió. |
| `docs/entrega/presentacion.pptx` (+ `.pdf`) | Presentación de entrega, 46 láminas. **Generada por código** desde `docs/entrega/deck/`; no se edita a mano. |
| `docs/entrega/guion-orador.md` | Notas de orador de las 46 láminas, generadas durante el build del deck. |
| `docs/entrega/arquitectura.md`, `docs/entrega/guion-demo.md` | Documento técnico de entrega y guion de la demo en vivo, alineados con el deck. |
| `README.md`, `backend/README.md`, `frontend/README.md` | Puesta en marcha. |

**No hay un "plan vigente" activo.** El anterior (`docs/superpowers/plans/2026-09-02-cierre-verificado.md`) fue borrado en una sesión previa sin commitear el borrado ni sustituirlo; este índice ya no lo referencia. Retomar el trabajo desde la sección "Qué falta" de abajo, verificada contra el código en este corte.

## Estado verificado (2026-09-02, noche)

### Gates

| Gate | Resultado medido |
|---|---|
| `make test-backend` (`uv run pytest`) | **500 passed**, 1 skipped (salida 0) — medido el 2026-09-03 |
| `make lint-backend` | OK |
| `make typecheck-backend` | 0 errores, 0 warnings, 0 informations |
| `make check-frontend` | lint + typecheck + **97 tests** en 17 ficheros + build, OK — medido el 2026-09-03 |
| `make check-openapi` | OK, sin drift |

### Defectos encontrados y corregidos en la verificación end-to-end

Cinco fallos reales que sólo aparecen ejecutando la aplicación, no leyendo el código:

1. **La tarjeta «Reglas evaluadas» salía vacía en modo Automático.** Había dos
   constructores de payload duplicados: el de los modos explícitos pasaba hechos y
   reglas, y el del reducer (el que usa Automático) devolvía `{convention, rules: []}`
   —y `rules` ni siquiera es el campo que lee la tarjeta—. Unificados en
   `frontend/src/lib/tool-call-payload.ts`, con un test que compara ambos caminos.
2. **El resultado era circular:** «El Convenio es aplicable» seguido de «Datos que
   faltan: determinar el convenio». Sustituido por los tres datos concretos que el
   manual exige (casillas del apartado 12, hechos de maniobra para una norma
   subsidiaria, o si consta D.A.A. conjunta), y la frase pasa a explicar que
   aplicabilidad y culpabilidad son dos planos distintos.
3. **La redacción de las reglas invertía su sentido:** `cide-requires-two-vehicles …
   No se cumple con vehicle_count=2` se leía como «no hay dos vehículos». Son reglas
   de exclusión: ahora dicen «No se activa con …», y una regla que sí se activa cita
   la consecuencia que su revisor firmó.
4. **El convenio estaba hardcodeado a ASCIDE** al resolver por una norma de maniobra.
   `cide-door-opening` es `kind: manoeuvre` pero es CIDE: se habría etiquetado mal en
   cuanto se le añadiera condición verificable. El convenio se lee ahora del artefacto
   firmado (campo `convention`, declarado en el schema y en las 8 reglas que lo tienen),
   y una regla que no lo declara resuelve **sin** nombrar convenio en lugar de suponerlo.
5. **El visor de PDF no pintaba nada.** Rasterizaba las 111 páginas del manual a canvas
   antes de mostrar la primera: abrir una cita dejaba un skeleton durante minutos.
   Ahora abre el documento, lee el número de páginas y rasteriza sólo la que se mira.
   Verificado en el navegador: la cita de la p. 9 abre la página 9 de 111 con el texto
   que la sustenta, y la navegación entre páginas es inmediata.

Además, el extractor de hechos inventaba maniobras (`exit_manoeuvre_by: B` en un alcance
en semáforo). El prompt acota ahora que un hecho de maniobra sólo se rellena si el relato
narra esa maniobra; comprobado que deja de emitirlos.

### Credenciales y servicios locales

Las claves de Langfuse (`LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`/`LANGFUSE_BASE_URL`/`LANGFUSE_PROJECT_ID`) estaban vacías en `.env`; `make serve-backend` las suplía por variable de entorno, pero cualquier otra vía de arranque quedaba sin trazas. Se han fijado explícitamente en `.env` (valores tomados de `ops/local.env`, ya provisionados en el compose). Verificado con trazas reales en la UI de Langfuse (`question_workflow`, `claim_workflow`, `OpenAI-generation`, `OpenAI-embedding`) bajo el proyecto `allianz-rag`.

Compose `allianz-rag` (Langfuse, langfuse-worker, ClickHouse, PostgreSQL, Redis, Qdrant, MinIO) verificado arriba y sano.

### Qué está hecho

- **Presentación de entrega (2026-09-03)**: `docs/entrega/presentacion.pptx`, 46 láminas
  generadas por código desde `docs/entrega/deck/` (pptxgenjs), con notas de orador en las 46 y
  un guion en markdown que sale del mismo build. Cubre lo que el enunciado pide explícitamente
  y no estaba: plan con hitos, supuestos, riesgos y el porqué de cada decisión técnica, además
  de una lámina de selección de modelos. Lleva **capturas reales del producto** tomadas con
  Playwright contra la aplicación en marcha. Todas las cifras se midieron contra este
  repositorio antes de generarla; la comprobación encontró y corrigió cuatro afirmaciones
  falsas (13 puertos de salida cuando son 12, la colisión en cadena citada como «págs. 57-58»
  cuando el ruleset firmado cita la 57, la página del caso del vehículo aparcado, y el golden
  dado por publicado como dataset en Langfuse cuando no lo está).
- **Ingestión**: contrato de publicación unificado; pypdf y Docling publican `original.pdf`. **Ambos parsers están publicados** para el documento verificado: `pypdf-6.16.2` (baseline, texto plano) y `docling-2.124.0-pdfium-5.13.0-rapidocr-latin-torch-r2-3d1d1af9689b76cf` (estructurado, con `regions`/bounding boxes verificadas en las 111 páginas). CLI `compare-parsers`. Páginas en blanco preservadas.
- **Índices Qdrant**: dos publicaciones verificadas — `baseline` (pypdf, chunking fijo, 118 fragmentos, **activa**) y `structured` (docling, chunking por secciones, 109 fragmentos, publicada pero **no activada** como demo). No se ha promovido `structured` a activa porque la spec exige selección por evaluación, no por disponibilidad («la disponibilidad de una técnica no demuestra que mejore los resultados»); con Docling ya publicado, esa comparación es ahora posible.
- **Perfiles e índices**: `IndexSignature` con 13 campos; CLI `index-rollback` y `list-index-versions`; `rollback_alias` verifica firma antes de mover el alias.
- **Recuperación**: densa + BM25 español + RRF nativo de Qdrant, intercambiables por configuración.
- **Workflows**: grafo documental (`retrieve → generate → validate`) y grafo de siniestros (`extract_facts → retrieve_criteria → apply_rules → explain → validate`). La extracción del LLM no puede sobrescribir el resultado determinista.
- **Reglas de aplicabilidad**: `domain/rules/applicability.py` implementa la puerta de dos vehículos, colisión directa, tercero identificado y colisión en cadena, con evidencia obligatoria. Verificado.
- **Reglas de maniobra (subsidiarias ASCIDE) — parcialmente machine-checkable**: `ascide-b10-lane-change` (cambio de carril reconocido por ambas partes + disparidad de versiones ⇒ culpable quien cambia de carril) tiene condición verificable y su resultado alimenta la decisión final: `build_applicability_analysis` produce `decision="resolved"` + convenio leído del artefacto cuando exactamente una regla de maniobra casa (y se mantiene `undetermined` si casan varias en conflicto). Verificado extremo a extremo con `accident-04-lane-change` (API y UI, con el modelo real).
- **Tabla de culpabilidad CIDE (18×18) conectada al flujo de siniestros.** Estaba transcrita y atestada (324 celdas) desde antes, con `lookup_daa_matrix` probado, pero nadie la llamaba: un siniestro con las casillas del apartado 12 declaradas se quedaba en «Convenio aplicable, culpabilidad sin determinar» para siempre. Ahora `decide_from_daa_matrix` (`domain/rules/cide_matrix.py`) distingue cuatro resultados que la interfaz no puede confundir: la tabla **atribuye** responsabilidad, la celda es un «-» y **no atribuye nada**, una de las **cuatro observaciones impresas** bajo la tabla (pág. 101 — «A2+B4 = Culpable B, salvo que el A abra la puerta») está **pendiente de su hecho decisorio**, o esa observación **se cumple y retira la atribución**. Las cuatro observaciones se declararon de forma estructurada en el artefacto firmado (`applies_to`/`exception_fact`/`exception_actor`/`liable_unless_exception`), nunca en código: una celda con asterisco sin observación anotada no decide. Verificado extremo a extremo con el modelo real: A1+B8 resuelve `applicable/CIDE/resolved` citando la celda; A2+B4 sin el hecho de la puerta abre una interrupción de LangGraph pidiendo exactamente el texto de la observación; con «B abrió la puerta» resuelve a B; con «A abrió la puerta» la excepción retira la atribución y queda `undetermined`, sin inventar quién responde.
  **Pendiente**: `ascide-b5-parked-vehicle`, `ascide-b6-exit-from-parking`, `ascide-b9-reverse-vs-rear-impact`, `ascide-b11-roundabout`, `ascide-traffic-light-amber` y `cide-door-opening` siguen sin condición verificable; devuelven `insufficient_data` de forma honesta, no un valor inventado.
- **Catálogo D.A.A.**: `data/rules/daa-circumstances.v1.json` fija y versiona las etiquetas `A0`–`A17`. El responsable del proyecto validó la correspondencia el 2026-09-02. Es una fuente externa al manual.
- **API**: sobre común tipado, JSON y SSE para consultas, `session_id` por hilo hasta los metadatos de Langfuse, casos de demo (`GET /api/v1/demo/cases`, ahora leídos desde el golden real sin exponer `expected_output`) y modo administrador de ingesta por API. La ingesta sólo acepta el manual verificado y publica el índice de forma atómica.
- **Frameworks de calidad**: CLI `golden validate/freeze/publish`, CLI `rules validate/compare-transcriptions`, schemas de matriz y ruleset con attestation obligatoria.
- **Casos de demo en castellano y variados**: `GET /api/v1/demo/cases` sirve ahora una
  selección curada (`DEFAULT_DEMO_CASE_IDS`) en castellano que cubre los tres
  comportamientos que hay que poder enseñar: un siniestro que se resuelve
  (`accident-04-lane-change-es`), uno en el que abstenerse es lo correcto
  (`accident-02-pile-up-es`), dos consultas documentales y **una pregunta fuera de
  alcance** (`fuera-de-alcance-es-01-baremo-lesiones`). El conjunto de desarrollo puede
  crecer sin inundar la interfaz. Verificado extremo a extremo: los cinco casos dan
  exactamente lo que dice el golden, incluida la abstención sin cifras de la pregunta
  trampa.
- **Golden set — desarrollo**: el conjunto actual son **110 casos** en `data/evaluation/golden/development.jsonl`, congelados como release `synthetic-expansion-110-2026-09-03` bajo `data/evaluation/golden/releases/` (items.jsonl SHA `73d0981b21a6d3db927c90d407f917785396aa97c79026ef7a618e3cf5283dc4`, schema SHA `3f70aa5a95036e36658e565ccc7994eba29e81ea4d0f62227cc443e143eb4a36`, schema v1.0.0). El merge final une:
  - **5 siniestros del enunciado** (`accident-01-rear-end` … `accident-05-alcohol-injury`) — la evidencia de aceptación de la entrevista, que la spec exige en `development` (sección 9).
  - **5 variantes ES** de releases anteriores (`accident-02-pile-up-es`, `accident-04-lane-change-es`, `consulta-es-01-alcoholemia`, `consulta-es-02-mas-de-dos-vehiculos`, `fuera-de-alcance-es-01-baremo-lesiones`) — preservadas tras la consolidación de los dos releases previos.
  - **100 casos sintéticos** en español (50 question + 50 claim, balance exacto 50/50).
  Se aplicaron **5 bounded fixes de schema** durante el merge (3 deduplicaciones de `evidence_requirements.all_of` / `provenance.source_ids`, 1 ASCII-fold de `alternative_id` con `ó`). La validación posterior pasa con `errors: []`, `item_count: 110`, `evidence_pool_size: 111`. Las releases antiguas (`v1-interview-2026-09-02`, `v2-es-2026-09-02`, `synthetic-expansion-2026-09-02`) están retiradas del árbol. Cada caso tiene el esquema completo (`input`/`expected_output`/`metadata`), con `applicability`/`convention`/`claim_decision` coherentes, requisitos verificables, alternativas aceptables, prohibiciones específicas y paquetes de evidencia AND/OR citando páginas reales del manual. **Revisión por IA** (no humana): tres pasos (`claude-authoring`, `claude-adversarial-review`, `claude-adjudication`). **Limitación declarada**: ningún caso tiene revisión de un experto humano del dominio; el set es **referencia sintética auditada contra el manual**, no baremo pericial. Sigue pendiente congelar una reserva (holdout) cuando se decida abrir evaluación final (de momento 0 en holdout, todo en development por criterio operativo de esta noche).

- **Bucle de evaluación — primera corrida completa** (`commit fe9aaed`, baseline runner + smoke en `data/evaluation/results/2026-09-03-smoke/`): 5 casos × 3 modos en 31.5s, 0 errores, contrato del runner validado.

- **Adapter fixes del adapter OpenAI (estabilidad del runner)** — dos bugs detectados en la primera corrida completa (commit `33bec4e` y `3b452ee`): (a) `AnswerSchema.to_application()` no deduplicaba `evidence_ids` repetidos dentro de un mismo bloque; (b) `ClaimExtractionSchema.to_application()` no descartaba facts/questions con `name`/`source_text`/`id`/`prompt`/`reason` whitespace-only (Pydantic `min_length=1` pasa pero el dataclass exige `.strip()` no vacío). Ambos TDD: tests rojos → fix → gates verdes. Erradican los 11/330 HTTP 500 que aparecían en la primera corrida.

- **Re-corrida post-fixes del adapter** (`commit fe9aaed`, `data/evaluation/results/2026-09-03-baseline-pre-ruleset-fix/`, 1379.9s, 329/330 OK, gpt-5.6-luna). Métricas crudas:

| Métrica | Valor | n |
|---|---|---|
| question answer_status_accuracy | 0.585 | 110 |
| question evidence_validity | 0.370 | 110 |
| claim applicability_accuracy | 0.829 | 39 |
| **claim convention_accuracy** | **0.120** | 39 |
| **claim claim_decision_accuracy** | **0.314** | 39 |
| claim evidence_validity | 0.526 | 39 |
| auto router_match | **0.964** | 110 |
| abstention correct_rate | 0.613 | — |
| unjustified_resolution_rate | 0.000 | — |
| router_confusion | 55/51/2/2 (claim→claim, q→q, claim→q, q→claim) | 110 |

- **Oracle Gate 1 sobre los números crudos** (`ora-2`): la accuracy cruda de convention/decision es engañosa. Cuando el ruleset dispara, el resultado suele ser correcto; el problema es que **no dispara** en ~19 de 25 mismatches porque modeló los guard negativos como `is_false` estricto (la nota de la regla decía "dispara salvo que se contradiga explícitamente", el motor lo modelaba como "dispara sólo si se constata el false"). El framing de "el workflow deja campos en None en lugar de undetermined explícito" se rechaza parcialmente: el workflow SÍ emite `undetermined`, el ruleset no dispara.

- **Fix del ruleset** (`commit 03922f8`): nuevo operador `is_false_or_absent` en `backend/src/domain/rules/ruleset.py` (helper `_optional_fields` que excluye estos campos del chequeo de hechos faltantes) + re-authoring de 2 reglas en `data/rules/ruleset.v1.json` (líneas 174 `exit_disputed_as_incorporation` en `ascide-b6-exit-from-parking` y 307 `door_opening_specified` en `cide-door-opening`). `is_false` estricto NO cambia (regression test incluido). 4 tests rojos primero, 506 tests verdes en total. Re-attestation pendiente — el `reviewer_id` se conserva, pero el contenido requiere sign-off explícito.

- **Restauración de borrado accidental** (`commit 1a56a8d`): el commit `03922f8` arrastró 20 archivos en `docs/entrega/deck/*` que no eran míos (lista explícita en el plan como "no borrar carpetas de otras sesiones sin incorporar su contenido"). Restaurados desde HEAD~1.

- **Re-corrida post-ruleset-fix NO EJECUTADA**: el usuario paró el run para no gastar más tokens. El fix está en `main` con tests verdes, pero las métricas reales que confirmen la subida esperada (Oracle: convention 0.120 → 0.50-0.65, claim_decision 0.314 → 0.55-0.70) no se han medido contra `development.jsonl`. Queda pendiente para cuando se autorice gasto LLM.

- **Pendientes del plan original**, deferred por presupuesto de tokens**:
  - Phase 3b: authoring de `applies_when` para reglas sin predicado (`ascide-b11-roundabout`, `convention-scope`).
  - Phase 3 revisión humana de etiquetas golden: 6 casos con conflicts matrix/applicability-vs-golden (`accident-03`, `synth-03`, `synth-20`, `synth-23`, `synth-31`, `synth-32`) — no tocar código, crear nota en `docs/superpowers/plans/2026-09-03-golden-label-review.md`.
  - Phase 3 endurecer extractor (Bug D de Oracle): mismo input produce `one_vehicle_parked='true'` (claim) y `one_vehicle_parked='A'` (auto).
  - Phase 4: jueces LLM (`faithfulness`, cumplimiento de requisitos) + calibración obligatoria contra errores conocidos.
  - Phase 5 (auditoría): `ascide-b11-roundabout` split en 2 reglas mutuamente excluyentes, stub de reranker, stub de visión (`profiles.py` tiene `reranker: Literal["none", "openai"]` y `vision: Literal["none", "openai-responses"]` declarados pero ningún adaptador real).
- **Frontend**: React 19 + Vite, chat con tool calls, visor PDF, sugerencias cargadas desde la API de demo, 92 tests unitarios, build limpio. El botón superior alterna entre modo administrador y volver al chat.
- **Historial real**: `lib/thread-store.ts` persiste hilos versionados en localStorage con tolerancia a datos corruptos, cuota y sandbox.
- **Duraciones del frontend**: verificado contra el código — **no fabrica duraciones**. `dispatchToolCallsFromEnvelope` en `routes/_index.tsx` omite deliberadamente `durationMs` cuando el backend no emite tiempos por etapa, y `tool-call-card.tsx` muestra "OK" en su lugar. La entrada anterior de este documento sobre `durationMs: 0` estaba obsoleta; el código ya lo corrigió antes de este corte.

### Qué falta — los agujeros reales

Ordenados por impacto sobre la entrega.

1. **El golden set no tiene revisión humana**, sólo revisión de tres pasos por IA (ver arriba). Sigue sin comparativa de recuperación, métricas de router publicadas ni holdout. Ampliar más allá de los 5 casos de entrevista con generación Ragas + revisión sigue pendiente.
   Además, **el golden no está publicado como dataset en el proyecto de Langfuse en uso**: la API de datasets del proyecto `cmtklzgpm000trm07om22hcpa` devuelve 0 (comprobado el 2026-09-03). `allianz golden publish` está pendiente de ejecutar contra ese proyecto.
2. **1 de las 14 reglas firmadas sigue sin condición machine-checkable**: `ascide-b11-roundabout` (rotondas), que tiene una excepción con **resultado alternativo** (no una simple retirada de atribución) — «culpable quien accede, salvo que ambos tengan daños laterales no angulares, en cuyo caso culpable el de daños en el lateral derecho» — y exigiría una segunda regla en el artefacto con su propio `applies_when` mutuamente excluyente, cambio más sustancial que rellenar un predicado existente. `convention-scope` (ámbito geográfico) tampoco es una regla de decisión y queda fuera de este recuento. Todas las demás (`ascide-b5`, `ascide-b6`, `ascide-b9`, `ascide-b10`, `ascide-traffic-light-amber`, `cide-door-opening`, `cide-matrix-lookup` con sus cuatro observaciones) están conectadas y verificadas con el modelo real.

   De paso se corrigieron dos patrones sistemáticos en el planificador de entrevista del LLM (misma llamada que extrae los hechos, antes de que las reglas se apliquen): confundía «el relato declara que un dato no consta» con «hay que preguntarlo» (rompía `cide-door-opening`, cuya condición de activación es precisamente esa ausencia), y confundía «disparidad de versiones» con «caso irresoluble» (rompía `ascide-b9`, `ascide-b10` y `ascide-b11`, que existen justamente para resolver esa disparidad). Ambos verificados 4/4 y 3/3 con el modelo real tras el ajuste del prompt. Sin ellas, un siniestro sin D.A.A. declarada ni maniobra reconocida (p. ej. `accident-01-rear-end` narrado sin casillas ni cambio de carril) seguirá devolviendo `undetermined` correctamente — es la respuesta correcta cuando el relato no las aporta, no una limitación oculta.
3. **El índice `structured` (Docling) está publicado pero no activo.** Falta la comparación de evaluación baseline-vs-structured que justifique (o no) promoverlo, y el CLI técnico `allianz index` no está expuesto por el modo administrador de la API (que sigue fijo a `pypdf`).
4. **Ningún miembro del equipo tiene cuenta propia en el proyecto Langfuse `allianz-rag`.** El proyecto sólo tiene al usuario de inicialización (`local@allianz.test`); una cuenta personal creada por el responsable del proyecto no está invitada a la organización `allianz-local`. No bloquea el funcionamiento (las claves de proyecto son independientes del login humano), pero si se quiere navegar la UI de Langfuse con una cuenta nominal, hace falta invitarla desde `Organization Settings → Members`.
5. **`data/evaluation/golden/development.jsonl` es el golden actual (110 casos: 5 enunciado + 5 ES variantes + 100 sintéticos)**, congelado como release `synthetic-expansion-110-2026-09-03` bajo `data/evaluation/golden/releases/`. Las releases `v1-interview-2026-09-02`, `v2-es-2026-09-02` y `synthetic-expansion-2026-09-02` (los 10 previos + los 100 sintéticos intermedios) se han retirado: están absorbidas dentro de los 110 casos vigentes. No hay todavía `holdout.jsonl`.

### Limitaciones que hay que declarar, no resolver

- **El manual no define qué maniobra es `A0`…`A17`.** Son casillas del apartado 12 del parte amistoso europeo (D.A.A.), un formulario externo al manual.
- **Cuatro de los cinco siniestros del enunciado caen fuera del Convenio o quedan condicionados/indeterminados sin más datos**, confirmado de forma independiente en la revisión del golden set actual (los cinco casos siguen presentes dentro de los 100, ahora como family_ids `accident-0X-…` con sus variantes ES): `accident-02-pile-up` (cinco vehículos y/o colisión en cadena, `not_applicable`), `accident-03-parked-hit-and-run` (segundo vehículo no identificado, `undetermined`/`conditional`), `accident-05-alcohol-injury` (aplicable pero sin maniobra que fijar la culpa material sin casillas DAA, `undetermined`; lesiones y lo penal fuera de alcance). `accident-01-rear-end` es `applicable` pero `undetermined` en cuanto a culpa (exige la matriz A0–A17, que el relato no aporta). Sólo `accident-04-lane-change` se resuelve (`resolved`, ASCIDE, norma b.10). Abstenerse con criterio es la respuesta correcta en los otros cuatro; la spec lo recoge: «no se exige inventar una conclusión definitiva».
- **La alcoholemia no excluye el Convenio** (p. 9 del manual). Lo penal y los daños personales sí quedan fuera del alcance convencional (p. 27 y p. 62 del manual, citadas ahora en el golden set).
- El manual es de 2004.

## Decisiones vigentes

1. Backend es la única fuente de verdad de etapas, timestamps y duraciones.
2. La matriz 18×18 no se autotranscribe desde tablas de Docling. Exige dos transcripciones independientes y adjudicación humana firmada.
3. `technical_fixture` se rechaza por defecto en cualquier release real.
4. El holdout se abre una sola vez, tras congelar código, prompts y reglas.
5. No se inventan métricas, trazas, tiempos, reglas evaluadas ni resultados.
6. Todo artefacto experimental identifica commit, hashes, perfil, prompts y modelos.
7. La configuración de demo (perfil `baseline` vs `structured`) se cambia por evaluación, no porque un índice nuevo exista.

## Decisiones humanas pendientes

1. Revisar por una persona experta del dominio (no sólo IA) los 5 casos del golden set antes de considerarlos `adjudicated` en un sentido pleno.
2. Añadir la excepción de resultado alternativo de `ascide-b11-roundabout` como segunda regla en el artefacto firmado.
3. Decidir, con una comparativa de evaluación baseline-vs-structured, si se promueve el índice Docling/structured a demo activa.
