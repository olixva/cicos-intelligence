# Arquitectura

Este documento describe cómo está construido el sistema que hay en este
repositorio: sus capas, sus flujos de ejecución y las decisiones que explican
por qué está hecho así.

## Visión general

CICOS Intelligence es un sistema RAG local sobre el *Manual de convenios
CIDE / ASCIDE / CICOS* (edición de noviembre de 2004, 111 páginas). Hace dos
cosas sobre esa fuente:

1. **Responde preguntas del manual** citando las páginas que sostienen cada
   afirmación, y se abstiene cuando la evidencia recuperada no basta.
2. **Analiza relatos de siniestro**: extrae los hechos del relato, aplica un
   conjunto de reglas firmadas derivadas del manual y devuelve si el Convenio
   es aplicable, cuál, y si se puede atribuir responsabilidad — o qué falta
   para poder hacerlo.

Un tercer modo, **automático**, clasifica la intención de la entrada y la
despacha a uno de los dos flujos anteriores.

```
   Navegador (SPA React)
        │  POST /api/v1/queries        (JSON)
        │  POST /api/v1/queries/stream (SSE)
        ▼
   FastAPI  ── sobre unificada por modo ──┐
        │                                 │
        ├── question ─▶ grafo documental ─┤
        ├── claim ────▶ grafo siniestros ─┤──▶ OpenAI (Responses API)
        └── auto ─────▶ router ───────────┘──▶ Qdrant (denso + BM25 + RRF)
                                          └──▶ Langfuse (trazas y prompts)
```

Todo corre en local: Qdrant y Langfuse (con su Postgres, ClickHouse, Redis y
MinIO) se levantan con Docker Compose. El único servicio externo es la API de
OpenAI, para embeddings y generación.

## Arquitectura hexagonal

El backend está organizado en cuatro capas, con las dependencias apuntando
siempre hacia dentro:

```
backend/src/
├── domain/            reglas y modelos del negocio; sin dependencias externas
│   ├── models/        ClaimInput, ClaimAnalysis, RuleEvaluation, PageEvidence…
│   └── rules/         aplicabilidad, motor de ruleset, tabla CIDE, validación
│                      de artefactos firmados
├── application/       orquestación; conoce el dominio y los puertos
│   ├── ports/
│   │   ├── inbound/   AnswerQuestion, AnalyzeClaim, ResolveQuery,
│   │   │              IngestDocument, InspectManual
│   │   └── outbound/  Retriever, LanguageModel, EmbeddingProvider,
│   │                  EvidenceRepository, DocumentParser, QueryClassifier…
│   ├── services/      lógica pura: chunking, citas, guardarraíles, routing,
│   │                  construcción del análisis de siniestro
│   └── use_cases/     implementación de los puertos de entrada
├── infrastructure/    adaptadores concretos
│   ├── adapters/inbound/   API FastAPI, CLI `allianz`
│   └── adapters/outbound/  Qdrant, OpenAI, Docling, pypdf, Langfuse,
│                           repositorio de evidencia en sistema de ficheros
└── bootstrap.py       raíz de composición: construye los objetos reales
```

El dominio no importa nada de infraestructura. Cada dependencia externa entra
por un puerto (`Protocol`) y se sustituye por un doble en los tests: la suite
completa corre sin OpenAI, sin Qdrant y sin Langfuse.

`bootstrap.py` es el único sitio que sabe qué implementación concreta se usa.
Las importaciones pesadas (Docling, Qdrant, LangGraph) son perezosas dentro de
las funciones de construcción, de modo que la CLI de inspección arranca sin
cargar el stack de ingesta.

## Los tres flujos

Cada flujo es un grafo de LangGraph con un presupuesto de tiempo propio. El
grafo es explícito para que las etapas sean observables: cada nodo produce una
observación en Langfuse y un *tool call* visible en la interfaz.

### Flujo documental (`mode=question`)

```
retrieve ──▶ generate ──▶ validate
```

- **retrieve**: consulta híbrida contra Qdrant (denso + BM25 español, fusión
  RRF nativa) sobre el alias `allianz-manual-active`.
- **generate**: llamada a OpenAI con salida estructurada. El prompt
  (`document-question`, versionado en Langfuse) obliga a responder sólo desde
  el contexto y a citar los `evidence_id` que sostienen cada bloque.
- **validate**: `application/services/question_answering.py` recorta las citas
  que el modelo no puede sostener. Un bloque debe citar **todos** los
  `evidence_id` de un grupo de contexto o ninguno; las citas parciales se
  descartan y la respuesta baja a `partial`, o a `insufficient_evidence` si no
  queda ningún bloque en pie. La validación es determinista y ocurre después
  del modelo: el modelo no puede autoacreditarse.

### Flujo de siniestros (`mode=claim`)

```
extract_facts ─▶ retrieve_criteria ─▶ apply_rules ─▶ plan_interview
                                                          │
                        ┌─────────────────────────────────┘
                        ▼
                 needs_information ──(faltan datos)──▶ interrupt ─▶ extract_facts
                        │
                        └──(suficiente)──▶ explain ─▶ validate
```

- **extract_facts**: el LLM extrae hechos tipados del relato (número de
  vehículos, colisión directa, casillas del apartado 12 de la D.A.A., quién
  cambia de carril, etc.) y propone un plan de entrevista. Los nombres de los
  hechos **se derivan del ruleset firmado**, no están escritos en el prompt: si
  se añade una regla que lee un hecho nuevo, el extractor empieza a pedirlo.
- **retrieve_criteria**: recupera del manual el criterio aplicable, para que la
  explicación se apoye en páginas reales.
- **apply_rules**: motor determinista. Evalúa la puerta de aplicabilidad, el
  ruleset firmado y, si procede, la tabla de culpabilidad CIDE. **La extracción
  del LLM no puede sobrescribir este resultado.**
- **plan_interview / needs_information**: si falta un dato decisorio, el grafo
  se detiene con un `interrupt` de LangGraph y devuelve la pregunta concreta.
  La respuesta del usuario vuelve como `clarifications` y el grafo se reanuda
  desde el checkpoint sin repetir lo ya establecido.
- **explain / validate**: se redacta el resultado y se comprueba la coherencia
  final (por ejemplo, una decisión `resolved` exige una regla que haya casado
  con su evidencia).

El detalle de las reglas está en [reglas-y-decision.md](reglas-y-decision.md).

### Flujo automático (`mode=auto`)

```
classify ─▶ dispatch ─┬─▶ to_question ─┐
                      ├─▶ to_claim ────┼─▶ wrap
                      └─▶ to_clarification ┘
```

El clasificador es una llamada a un modelo barato con un enum cerrado
(`question | claim | clarification_required`) y el prompt `auto-router`
versionado en Langfuse. Una decisión fuera del enum es un error, no un valor
por defecto.

Sobre esa decisión hay un **override heurístico**: si el router no dice
`claim` pero el texto contiene vocabulario inequívoco de relato de siniestro,
se fuerza `claim`. El motivo es concreto: el router barato confundía palabras
incidentales («no consigue detenerse a **tiempo**») con preguntas
meteorológicas, y un alcance trasero se quedaba sin analizar. La misma
heurística (`application/services/claim_heuristics.py`) exime a esos relatos
del guardarraíl de clima.

Los modos explícitos **nunca** pasan por el router: si el cliente dice
`question` o `claim`, esa es su decisión, no una sugerencia.

## Evidencia: identidad antes que contenido

Toda cita del sistema es un `evidence_id` con esta forma:

```
sha256:<hash del documento>:page:<página física del PDF>
```

Es una identidad, no un puntero a texto. Con ella el frontend puede abrir el
PDF original en esa página y el usuario ve la fuente, no una paráfrasis. Las
publicaciones de ingesta preservan **todas** las páginas físicas, incluidas
las que están en blanco, para que la numeración nunca se desplace.

Ver [ingesta-y-recuperacion.md](ingesta-y-recuperacion.md) para el contrato de
publicación completo.

## Decisiones de diseño

**El backend es la única fuente de verdad de etapas, tiempos y trazas.** El
frontend no fabrica duraciones: cuando el backend no emite un tiempo por
etapa, la tarjeta de *tool call* muestra «OK» en lugar de un número inventado.

**Los resultados deterministas mandan sobre el LLM.** El modelo extrae hechos
y redacta; no decide. La aplicabilidad, el convenio y la atribución salen de
reglas firmadas y de una tabla transcrita, evaluadas en código.

**Abstenerse es un resultado, no un fallo.** `undetermined`,
`insufficient_evidence` y `not_applicable` son respuestas de primera clase con
su propia explicación de qué falta. Cuatro de los cinco siniestros del
enunciado caen fuera del Convenio o quedan indeterminados sin más datos, y esa
es la respuesta correcta.

**Nada de placeholders en la auditoría.** `rules_evaluated` sólo contiene
reglas que realmente corrieron, con sus entradas, su resultado y las páginas
del manual que las sostienen. Una regla que no pudo evaluarse aparece como
`insufficient_data`, con el hecho que le faltaba.

**Un índice se identifica por su firma completa.** `IndexSignature` reúne
trece campos (hash del documento, parser, chunker, modelo y dimensiones de
embedding, idioma léxico, modo de recuperación, fusión, versiones de prompt…).
Consultar un índice con una firma incompatible es un error, no una
degradación silenciosa.

**Idempotencia y atomicidad en la ingesta.** El repositorio escribe una
publicación temporal completa y la renombra al directorio definitivo. Un
`publication.json` liga todos los ficheros por SHA-256 antes de que nadie lea
la evidencia.

## Frontend

SPA de React 19 + Vite que consume la sobre unificada. El estado del hilo es
un reducer puro (`lib/thread-state.ts`) alimentado 1:1 por los eventos SSE del
backend (`started | stage | completed | failed`), con transporte propio sobre
`eventsource-parser`. Los tipos del API se generan desde
`docs/api/openapi.json`, así que un cambio de contrato rompe el `typecheck`.

Detalle en [frontend/README.md](../frontend/README.md).

## Observabilidad

Cada petición lleva un `request_id` propio y, cuando hay Langfuse
configurado, un `trace_id` y un enlace directo a la traza. Los grafos abren un
span de Langfuse alrededor del despacho para que las llamadas a OpenAI queden
anidadas bajo la traza del workflow en lugar de aparecer sueltas. Los prompts
de generación y de routing viven en Langfuse con número de versión y se
aprovisionan de forma idempotente con `make provision-prompts`.
