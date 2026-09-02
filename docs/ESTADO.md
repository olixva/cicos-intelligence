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
| `docs/evaluation/coverage-matrix.md` | Diseño de cobertura del golden. Hoy hay 10 casos admitidos: los 5 de entrevista y 5 en castellano. |
| `docs/evaluation/golden-set-source-map.md` | Mapa de evidencias de los cinco siniestros. Verificado contra `pages.jsonl`. |
| `docs/rules/transcription-protocol.md` | Protocolo de doble transcripción de la matriz. |
| `docs/ingestion-baseline.md`, `docs/ingestion/parser-comparison.md` | Extracción baseline y comparativa de parsers. |
| `docs/operations/local-services.md` | Operación de los servicios locales. |
| `docs/enunciado/GenAI_Interview_Instructions.docx` | Enunciado original, tal como se recibió. |
| `docs/entrega/arquitectura.md`, `docs/entrega/guion-demo.md` | Recreados en este corte tras la pérdida sin commitear de la versión anterior. |
| `README.md`, `backend/README.md`, `frontend/README.md` | Puesta en marcha. |

**No hay un "plan vigente" activo.** El anterior (`docs/superpowers/plans/2026-09-02-cierre-verificado.md`) fue borrado en una sesión previa sin commitear el borrado ni sustituirlo; este índice ya no lo referencia. Retomar el trabajo desde la sección "Qué falta" de abajo, verificada contra el código en este corte.

## Estado verificado (2026-09-02, noche)

### Gates

| Gate | Resultado medido |
|---|---|
| `make test-backend` (`uv run pytest`) | **422 passed**, 1 skipped (salida 0) |
| `make lint-backend` | OK |
| `make typecheck-backend` | 0 errores, 0 warnings, 0 informations |
| `make check-frontend` | lint + typecheck + **96 tests** + build, OK |
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

- **Ingestión**: contrato de publicación unificado; pypdf y Docling publican `original.pdf`. **Ambos parsers están publicados** para el documento verificado: `pypdf-6.16.2` (baseline, texto plano) y `docling-2.124.0-pdfium-5.13.0-rapidocr-latin-torch-r2-3d1d1af9689b76cf` (estructurado, con `regions`/bounding boxes verificadas en las 111 páginas). CLI `compare-parsers`. Páginas en blanco preservadas.
- **Índices Qdrant**: dos publicaciones verificadas — `baseline` (pypdf, chunking fijo, 118 fragmentos, **activa**) y `structured` (docling, chunking por secciones, 109 fragmentos, publicada pero **no activada** como demo). No se ha promovido `structured` a activa porque la spec exige selección por evaluación, no por disponibilidad («la disponibilidad de una técnica no demuestra que mejore los resultados»); con Docling ya publicado, esa comparación es ahora posible.
- **Perfiles e índices**: `IndexSignature` con 13 campos; CLI `index-rollback` y `list-index-versions`; `rollback_alias` verifica firma antes de mover el alias.
- **Recuperación**: densa + BM25 español + RRF nativo de Qdrant, intercambiables por configuración.
- **Workflows**: grafo documental (`retrieve → generate → validate`) y grafo de siniestros (`extract_facts → retrieve_criteria → apply_rules → explain → validate`). La extracción del LLM no puede sobrescribir el resultado determinista.
- **Reglas de aplicabilidad**: `domain/rules/applicability.py` implementa la puerta de dos vehículos, colisión directa, tercero identificado y colisión en cadena, con evidencia obligatoria. Verificado.
- **Reglas de maniobra (subsidiarias ASCIDE) — parcialmente machine-checkable**: de las 14 reglas firmadas, 6 sólo estaban documentadas (`applies_when` ausente ⇒ siempre `insufficient_data`, por diseño: "documentada pero no verificable automáticamente"), incluida `ascide-b10-lane-change`. Se ha añadido la condición verificable de **`ascide-b10-lane-change`** (cambio de carril reconocido por ambas partes + disparidad de versiones ⇒ culpable quien cambia de carril) y se ha conectado su resultado a la decisión final: `build_applicability_analysis` ahora produce `decision="resolved"` + `convention="ASCIDE"` cuando exactamente una regla de maniobra casa (y se mantiene `undetermined` si casan varias en conflicto, para no adivinar). Verificado extremo a extremo con el caso `accident-04-lane-change` (API y UI). **Pendiente**: `ascide-b5-parked-vehicle`, `ascide-b6-exit-from-parking`, `ascide-b9-reverse-vs-rear-impact`, `ascide-b11-roundabout`, `ascide-traffic-light-amber`, `cide-matrix-lookup`, `cide-door-opening` y `convention-scope` siguen sin condición verificable; siguen devolviendo `insufficient_data` de forma honesta, no un valor inventado.
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
- **Golden set — desarrollo**: los 5 casos de la entrevista tienen ahora entradas completas y válidas contra el schema (`input`/`expected_output`/`metadata`), con `applicability`/`convention`/`claim_decision`, requisitos, alternativas aceptables, prohibiciones y paquetes de evidencia AND/OR citando páginas reales del manual (incluidas las páginas 27 y 62, "Daños distintos a los propios del vehículo" y "Lesiones", para la exclusión de daños personales — no citadas antes). **Revisión de tres pasos con IA (no humana)**: resolución independiente ciega → revisión adversarial independiente → adjudicación, documentado por caso en `metadata.review`. `allianz golden validate` pasa sin errores (`item_count: 5`, `evidence_pool_size: 111`); congelado y publicado en el dataset `allianz-rag-golden` de Langfuse. Una **segunda
  revisión adversarial** (independiente, contexto limpio) encontró defectos reales en los
  cinco casos ingleses y en los cinco nuevos: paquetes de evidencia AND que exigían
  páginas que no enuncian la regla, requisitos sin cita que los sostuviera, la
  calificación de «colisión en cadena» exigida por silencio, y —el hallazgo de más
  fondo— que las **normas subsidiarias son el quinto criterio** del orden de prioridad
  ASCIDE ante versiones contradictorias (pág. 111), que ningún caso mencionaba. Todo
  adjudicado e incorporado. El conjunto admitido son ahora **10 casos**, congelados como
  release `v2-es-2026-09-02`. **Limitación declarada**: ningún caso tiene revisión de un experto humano del dominio; `reviewer_ids` lo deja explícito (`claude-primary-resolution`, `claude-adversarial-review`, `claude-adjudication`). Sigue pendiente ampliar más allá de los 5 casos de entrevista y congelar una reserva (holdout).
- **Frontend**: React 19 + Vite, chat con tool calls, visor PDF, sugerencias cargadas desde la API de demo, 92 tests unitarios, build limpio. El botón superior alterna entre modo administrador y volver al chat.
- **Historial real**: `lib/thread-store.ts` persiste hilos versionados en localStorage con tolerancia a datos corruptos, cuota y sandbox.
- **Duraciones del frontend**: verificado contra el código — **no fabrica duraciones**. `dispatchToolCallsFromEnvelope` en `routes/_index.tsx` omite deliberadamente `durationMs` cuando el backend no emite tiempos por etapa, y `tool-call-card.tsx` muestra "OK" en su lugar. La entrada anterior de este documento sobre `durationMs: 0` estaba obsoleta; el código ya lo corrigió antes de este corte.

### Qué falta — los agujeros reales

Ordenados por impacto sobre la entrega.

1. **Falta la presentación PowerPoint de la entrevista** (`docs/entrega/presentacion.pptx`). Se recrean en este corte `docs/entrega/arquitectura.md` y `docs/entrega/guion-demo.md` (perdidos sin commitear en una sesión previa) y se genera el `.pptx` a partir de ellos.
2. **El golden set no tiene revisión humana**, sólo revisión de tres pasos por IA (ver arriba). Sigue sin comparativa de recuperación, métricas de router publicadas ni holdout. Ampliar más allá de los 5 casos de entrevista con generación Ragas + revisión sigue pendiente.
3. **8 de las 14 reglas firmadas siguen sin condición machine-checkable** (`ascide-b5-parked-vehicle`, `ascide-b6-exit-from-parking`, `ascide-b9-reverse-vs-rear-impact`, `ascide-b11-roundabout`, `ascide-traffic-light-amber`, `cide-matrix-lookup`, `cide-door-opening`, más `convention-scope`). Sólo `ascide-b10-lane-change` se completó en este corte; las 6 restantes ya declaran su convenio en el artefacto, que es el dato que faltaba para poder completarlas sin suponerlo. Sin ellas, los siniestros que dependen de esas normas (p. ej. `accident-01-rear-end`, que exige la matriz A0–A17) seguirán devolviendo `undetermined` correctamente pero sin resolución determinista posible con los datos del relato — ésa es, de hecho, la respuesta correcta para esos casos según la revisión del golden set.
4. **El índice `structured` (Docling) está publicado pero no activo.** Falta la comparación de evaluación baseline-vs-structured que justifique (o no) promoverlo, y el CLI técnico `allianz index` no está expuesto por el modo administrador de la API (que sigue fijo a `pypdf`).
5. **Ningún miembro del equipo tiene cuenta propia en el proyecto Langfuse `allianz-rag`.** El proyecto sólo tiene al usuario de inicialización (`local@allianz.test`); una cuenta personal creada por el responsable del proyecto no está invitada a la organización `allianz-local`. No bloquea el funcionamiento (las claves de proyecto son independientes del login humano), pero si se quiere navegar la UI de Langfuse con una cuenta nominal, hace falta invitarla desde `Organization Settings → Members`.
6. **`data/evaluation/golden/development.jsonl` fue el único artefacto de golden**; ahora también existe `data/evaluation/golden/releases/v1-interview-2026-09-02/` (manifest, items, schema) como instantánea congelada. No hay todavía `holdout.jsonl`.

### Limitaciones que hay que declarar, no resolver

- **El manual no define qué maniobra es `A0`…`A17`.** Son casillas del apartado 12 del parte amistoso europeo (D.A.A.), un formulario externo al manual.
- **Cuatro de los cinco siniestros del enunciado caen fuera del Convenio o quedan condicionados/indeterminados sin más datos**, confirmado de forma independiente en la revisión del golden set de este corte: `accident-02-pile-up` (cinco vehículos y/o colisión en cadena, `not_applicable`), `accident-03-parked-hit-and-run` (segundo vehículo no identificado, `undetermined`/`conditional`), `accident-05-alcohol-injury` (aplicable pero sin maniobra que fijar la culpa material sin casillas DAA, `undetermined`; lesiones y lo penal fuera de alcance). `accident-01-rear-end` es `applicable` pero `undetermined` en cuanto a culpa (exige la matriz A0–A17, que el relato no aporta). Sólo `accident-04-lane-change` se resuelve (`resolved`, ASCIDE, norma b.10). Abstenerse con criterio es la respuesta correcta en los otros cuatro; la spec lo recoge: «no se exige inventar una conclusión definitiva».
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
2. Añadir condiciones verificables (`applies_when`) para las 7 reglas de maniobra/matriz restantes, y revisarlas como se hizo con `ascide-b10-lane-change`.
3. Decidir, con una comparativa de evaluación baseline-vs-structured, si se promueve el índice Docling/structured a demo activa.
