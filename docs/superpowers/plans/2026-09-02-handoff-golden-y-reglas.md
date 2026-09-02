# Handoff — evaluación autónoma nocturna + golden set + specs al 100%

Prompt autocontenido. Pégalo entero en una sesión nueva. **El usuario ha dicho
explícitamente que va a dejar esto corriendo toda la noche sin supervisión: actúa de
forma autónoma, no pares a pedir confirmación para las acciones normales de este
proyecto** (editar código y datos, ejecutar evaluaciones que cuestan dinero real en
OpenAI, comitear, hacer push a `main`). Las únicas excepciones — cosas que sí deben
parar y preguntar — están marcadas explícitamente más abajo.

---

## 0. Contexto del proyecto y disciplina de trabajo

`prueba-allianz` es un asistente RAG local sobre el manual CIDE/ASCIDE/CICOS (111
páginas, SHA-256 `b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344`,
edición de noviembre de 2004). Repo en `/Users/aoc/proyectos/prueba-allianz`, rama
`main`, se trabaja y se sube **directo a main** (sin PR) tras verificar los gates.
Backend Python/FastAPI/LangGraph en `backend/`, frontend React en `frontend/`.
Arranque: `make local-services-up` (Qdrant/Langfuse/Postgres/Redis/ClickHouse/MinIO),
luego `make serve-backend` y `make serve-frontend`.

Specs de autoridad, en este orden de lectura:
1. `docs/superpowers/specs/2026-08-31-allianz-rag-design.md` — diseño consolidado.
2. `docs/architecture/2026-08-31-api-y-experiencia-propuesta.md` — contratos HTTP/UX.
3. `docs/architecture/2026-08-31-stack-tecnologico-propuesto.md` — stack.
4. `docs/evaluation/2026-08-31-golden-set-y-metricas-rag.md` — golden set y métricas.
5. `docs/ESTADO.md` — estado verificado a fecha de la última sesión. **Verifica sus
   afirmaciones contra el código, no las des por buenas**: el propio documento avisa
   de que quedó con referencias muertas una vez.

Disciplina aplicada en los últimos commits (`git log --oneline -20` para ver el
estilo real):

- TDD real: test en rojo antes que la implementación.
- Nunca fingir cobertura. Una regla o métrica sin evidencia verificable se declara
  como tal (`insufficient_data`, "no ejecutado", lo que corresponda), nunca se
  adivina ni se rellena con un valor inventado.
- **Verificar con el modelo real** (`make serve-backend` levantado, llamadas HTTP de
  verdad), no sólo con dobles de test — hay variabilidad del LLM; repite 3-4 veces
  antes de decidir si algo está arreglado o es ruido.
- Antes de cada commit: `cd backend && uv run pytest -q`, luego desde la raíz
  `make lint-backend`, `make typecheck-backend`, `make check-openapi` — los cuatro en
  verde. Si tocas frontend, también `make check-frontend`.
- Commits explicando el *porqué*. `git push origin main` después de verificar.
- `git fetch origin` antes de tocar nada: puede haber commits de otras sesiones en
  paralelo (ha pasado ya varias veces en este proyecto).

### Lo único que SÍ debe parar y preguntar (excepciones a la autonomía)

- Cualquier operación destructiva de git (`reset --hard`, `push --force`, borrar
  ramas) — no debería hacer falta ninguna para este trabajo.
- Borrar carpetas de trabajo de otras sesiones (`data/evaluation/golden/_drafts/`,
  `synthetic-expansion-2026-09-02/`, `.tmp_allianz_deck/`) sin haber incorporado o
  descartado conscientemente su contenido primero.
- Tocar `docs/entrega/presentacion.pptx` (tiene cambios locales sin comitear de una
  edición manual en LibreOffice; no lo sobrescribas).
- Subir el gasto en OpenAI de forma descontrolada: usa `gpt-5.6-luna` para iterar y
  reserva `gpt-5.6-sol`/`gpt-5.6-terra` (ya configurados como modelo de respuesta y
  de extracción en `.env`) para las pasadas que de verdad se van a medir. Respeta
  `ALLIANZ_LANGFUSE_MAX_CONCURRENCY` (por defecto 4, en
  `backend/src/infrastructure/adapters/outbound/evaluation/langfuse_experiments.py`)
  en vez de subir la concurrencia sin más.

---

## 1. ALERTA — `development.jsonl` está en riesgo de perder trabajo ahora mismo

`git status` mostrará `data/evaluation/golden/development.jsonl` como **modificado
sin comitear**. Alguien (otra sesión, generando un golden sintético de 100 casos) lo
**sobrescribió** con esos 100 casos nuevos, perdiendo los 10 que ya estaban en `main`
(commit `c92127c`): los 5 accidentes originales del enunciado
(`accident-01-rear-end` … `accident-05-alcohol-injury`) y 5 casos en castellano
(`accident-04-lane-change-es`, `accident-02-pile-up-es`, `consulta-es-01-alcoholemia`,
`consulta-es-02-mas-de-dos-vehiculos`, `fuera-de-alcance-es-01-baremo-lesiones`).
Verifícalo tú mismo:

```bash
git diff --stat HEAD -- data/evaluation/golden/development.jsonl   # 100 insertions, 10 deletions
python3 -c "
import json
ids = {json.loads(l)['metadata']['case_id'] for l in open('data/evaluation/golden/development.jsonl') if l.strip()}
required = ['accident-01-rear-end','accident-02-pile-up','accident-03-parked-hit-and-run','accident-04-lane-change','accident-05-alcohol-injury']
print([r for r in required if r not in ids], 'AUSENTES' if any(r not in ids for r in required) else 'todos presentes')
"
```

**La spec exige explícitamente que los cinco casos del enunciado permanezcan en
desarrollo** (`docs/superpowers/specs/2026-08-31-allianz-rag-design.md`, sección 2 y
9). No están opcionalmente ahí — son la evidencia de aceptación de la entrevista.

### Qué hacer

1. Recupera los 10 casos perdidos desde `main`:
   `git show c92127c:data/evaluation/golden/development.jsonl > /tmp/original-10.jsonl`
2. Fusiona (concatena por `case_id` único) los 10 originales + los 100 sintéticos en
   un único `development.jsonl` de 110 casos. No sobrescribas, une.
3. Arregla los 5 errores de schema que ya identifiqué en los 100 casos sintéticos
   (siguen sin arreglar, verificado ahora mismo con `allianz golden validate
   --golden-root ../data/evaluation/golden --evidence-root ../data/extractions`
   desde `backend/`):
   - `consulta-synth-09-colision-directa-definicion` — `evidence_requirements` con
     un `all_of` que repite un evidence_id.
   - `siniestro-synth-05-rotonda-partida` — `metadata.provenance.source_ids` repite
     un valor.
   - `consulta-synth-16-limite-perdida-total` — mismo problema de duplicados en
     `evidence_requirements`.
   - `consulta-synth-40-restos-fuera-perdida-total` — `provenance.source_ids`
     repetido.
   - `consulta-synth-42-pupilaje-baja-fuera` — `alternative_id:
     "alt-cobertura-póliza"` usa un carácter (`ó`) fuera del patrón permitido
     (`[A-Za-z0-9._:-]`); renómbralo a `alt-cobertura-poliza`.
4. Revalida hasta `errors: []`, `item_count: 110`.
5. **Cobertura que sigue faltando incluso con los 110** (ver `docs/evaluation/
   coverage-matrix.md` y la sección 2.2 de la spec de golden): los 100 sintéticos son
   100% español, `provenance.kind: "manual_derived"` — nada en inglés, nada
   `adversarial` (hechos inventados, citas incorrectas, instrucciones maliciosas
   insertadas en el contexto), nada marcado `interview_example` salvo los 5
   originales que hay que reincorporar. Si tienes tiempo tras el bucle de evaluación
   (sección 3), amplía con esas familias — no es bloqueante para empezar a evaluar.
6. Congela y publica: `allianz golden freeze --golden-root ../data/evaluation/golden
   --evidence-root ../data/extractions --dataset allianz-rag-golden --release
   <fecha>-110-casos`, luego `allianz golden publish --release <ese-nombre>
   --golden-root ../data/evaluation/golden` (necesita Langfuse arriba con las claves
   de `.env`).
7. Actualiza `docs/ESTADO.md` y `docs/entrega/arquitectura.md` con el recuento real.

No borres `_drafts/` ni `synthetic-expansion-2026-09-02/` sin haber incorporado su
contenido primero.

---

## 2. Foco principal — bucle de evaluación autónomo (esto es lo que debe correr toda la noche)

**Esto es lo más importante de este documento.** La evaluación de la spec
(`docs/evaluation/2026-08-31-golden-set-y-metricas-rag.md`, secciones 3 y 5) nunca se
ha ejecutado: no existe `data/evaluation/results/`, no hay holdout, no hay una sola
métrica publicada. El runner nativo de Langfuse está cableado pero **sólo para el
recorrido de preguntas** (`build_question_task` en
`backend/src/infrastructure/adapters/outbound/evaluation/langfuse_experiments.py`,
que llama a `build_answer_question`); no existe el equivalente para siniestros
(`build_answer_question` → `build_answer_claim`/`AnalyzeClaim`, puerto en
`backend/src/application/ports/inbound/analyze_claim.py`) ni para el router
(`ResolveQuery`, `backend/src/application/ports/inbound/resolve_query.py`). De las
~20 métricas concretas de la sección 3 de la spec, sólo hay **una implementada**:
`FactualCorrectness` (F1 factual, Ragas) en
`backend/src/infrastructure/adapters/outbound/evaluation/ragas_evaluators.py`. Las
comprobaciones deterministas en `domain_evaluators.py` cubren cobertura de evidencia
AND/OR y precisión/recall de citas por ID — nada de exactitud de decisiones de
dominio, tasa de hechos inventados, abstención correcta/innecesaria, ni matriz de
confusión del router.

### Protocolo — no lo saltes, está en la spec por una razón concreta

Antes de tocar nada de código para "mejorar métricas", separa una **reserva
(holdout)** del golden ya fusionado (sección 2.6 de la spec de golden set): coge una
porción (orientativamente 20 de los 110-130 casos, sin cruzar `family_id` con
desarrollo) y muévela a `data/evaluation/golden/holdout.jsonl`. **A partir de ese
momento, todo el ciclo de evaluar→ajustar→reevaluar de esta noche usa SOLO
`development.jsonl`.** No mires ni evalúes contra el holdout durante los ajustes —
es exactamente la separación que la spec exige para poder afirmar generalización al
final, y romperla invalida cualquier métrica que saques luego. Dejar el holdout para
un cierre final (si te da tiempo) es una mejora, no un requisito de esta noche.

### Paso a paso

1. **Completa primero los evaluadores deterministas** (baratos, sin llamadas a LLM,
   TDD como el resto del proyecto) en
   `backend/src/infrastructure/adapters/outbound/evaluation/domain_evaluators.py`:
   - Exactitud y macro-F1 de `applicability`/`convention`/`claim_decision` contra
     `expected_output.decisions` del golden.
   - Tasa de hechos inventados: hechos en `ClaimAnalysis.facts` sin respaldo en
     `expected_output` ni en `forbidden_facts` cumplidos.
   - Tasa de conclusión definitiva injustificada: `decision == "resolved"` cuando el
     golden esperaba `conditional`/`undetermined`/`not_assessed`.
   - Abstención correcta vs innecesaria (comparando `decision` real contra el
     esperado en los casos donde el golden marca indeterminación a propósito).
   - Router: exactitud, macro-F1 y matriz de confusión sobre `resolved_mode` vs
     `metadata.expected_intent`, aislado (modo explícito) y en Automático — sección
     3.7 de la spec de golden set: son dos lecturas distintas, no las mezcles.
   - Validez de referencias: cada `evidence_id` citado existe de verdad en
     `data/extractions/<hash>/<parser>/pages.jsonl` (ya hay algo parecido en
     `release_validation.py`, reutilízalo si aplica).

2. **Construye las tareas de experimento que faltan**, siguiendo el patrón exacto de
   `build_question_task` (mismo fichero): una para `AnalyzeClaim`/siniestros y otra
   para `ResolveQuery`/Automático. Cada una serializa la ejecución real (mismo caso
   de uso que usa la API, nunca un camino paralelo) para que el evaluador la
   consuma. El callback del runner de Langfuse **nunca** debe pasar
   `expected_output` al caso de uso — sólo al evaluador (ya está así de diseñado en
   `build_question_task`, respeta el mismo patrón).

3. **Ejecuta contra `development.jsonl` completo** con los tres recorridos
   (preguntas, siniestros, router aislado y en Automático), primero sólo con los
   evaluadores deterministas del paso 1 (barato, rápido, dale varias vueltas).
   Guarda cada corrida con su manifiesto (versión de dataset, modelos, prompts,
   commit) en `data/evaluation/results/<fecha>-<nombre-corrida>/` — no hay que
   inventar el formato, sigue el patrón de manifiestos ya usado en
   `release_validation.py`/`golden_schema.py` (hashes, versiones, nada implícito).

4. **Analiza los fallos por familia y por dimensión**, exactamente como se hizo esta
   sesión con las reglas del ruleset: cuando algo falla sistemáticamente (no una vez
   al azar — repite 3-4 veces), busca la causa raíz antes de tocar nada. Los dos
   bugs reales que se encontraron así en la sesión anterior:
   - El planificador de entrevista del LLM confundía "el relato declara que un dato
     no consta" con "hay que preguntarlo", y "disparidad de versiones" con "caso
     irresoluble" — ambos rotos en el prompt de
     `backend/src/infrastructure/adapters/outbound/language_model/
     openai_claim_fact_extractor.py`, no en el motor de reglas.
   - `ascide-b11-roundabout` sigue sin conectar (ver sección 4.1) — cualquier caso
     de rotonda dará `undetermined` correctamente pero sin resolución, y eso va a
     aparecer en las métricas como una familia entera con cobertura baja. No es un
     bug, es un hueco conocido: documéntalo en el análisis en vez de "arreglarlo"
     ajustando el juez para que no lo penalice.

5. **Aplica ajustes acotados con TDD** cuando la causa esté clara: prompts, reglas
   nuevas o completadas (siguiendo `data/rules/ruleset.v1.json`, nunca inventando un
   `applies_when` sin evidencia del manual), código del motor de reglas. Cada ajuste:
   test en rojo → arreglo → verde → verificar con el modelo real 3-4 veces →
   gates → commit con el porqué → push. No acumules cambios sin comitear durante
   horas — si el proceso se corta a mitad de noche, el trabajo ya hecho debe estar a
   salvo en `main`.

6. **Vuelve a ejecutar contra `development.jsonl`** tras cada tanda de ajustes y
   compara contra la corrida anterior (mismo dataset, mismo commit de referencia
   documentado). Repite el ciclo 4→5→6.

7. **Añade las métricas de jueces LLM (Ragas) progresivamente**, no todas a la vez:
   empieza por ampliar `ragas_evaluators.py` con faithfulness y cumplimiento de
   requisitos (las dos siguientes más baratas/directas de la tabla de la sección
   3.2 de la spec de golden), antes que las de robustez (sección 3.4, que exigen
   fixtures sintéticos con ruido/paráfrasis controlados — más caras, déjalas para el
   final si te queda tiempo). **Antes de usar cualquier juez LLM para decidir algo,
   calíbralo** (sección 4 de la spec de golden): monta un pequeño conjunto de
   calibración con errores conocidos y verifica que el juez los detecta antes de
   fiarte de su puntuación en el resto del golden.

### Criterio de parada (para que esto no corra sin control toda la noche sin sentido)

No hay un número mágico de iteraciones correcto, pero fija uno y respétalo para no
quedarte en un bucle improductivo: por ejemplo, **detén el ciclo de ajustes cuando
dos rondas seguidas no cambien ninguna métrica agregada de forma significativa**, o
cuando lleves ~8 horas de trabajo efectivo, lo que ocurra antes. Cuando pares (por
criterio de parada o porque se acaba la noche), deja un resumen claro en
`docs/ESTADO.md` de: qué corridas se ejecutaron, qué métricas salieron, qué se
ajustó y por qué, y qué queda pendiente — con números reales, nunca estimados ni
inventados. Si una corrida no llegó a completarse, dilo explícitamente en vez de
omitirla.

---

## 3. Auditoría detallada — qué falta para que la spec funcione al 100%

Verificado contra el código en esta sesión, no copiado de la spec. Formato: qué pide
la spec → qué hay hoy → qué falta exactamente y dónde.

### 3.1 Reglas y motor determinista (`data/rules/ruleset.v1.json`)

- **13 de 14 reglas conectadas** con `applies_when` verificable y convenio leído del
  artefacto. Falta sólo **`ascide-b11-roundabout`**: su excepción tiene un
  **resultado alternativo** ("culpable quien accede a la rotonda, salvo que ambos
  tengan daños laterales no angulares, en cuyo caso culpable el de daños en el
  lateral derecho", manual pág. 75), no una simple retirada de atribución como las
  cuatro observaciones de la matriz CIDE. El motor (`evaluate_ruleset` en
  `backend/src/domain/rules/ruleset.py`) sólo soporta un `applies_when` con un
  outcome fijo por regla, así que hacen falta **dos reglas mutuamente excluyentes**
  en el artefacto (una para el caso general, otra para la excepción), con un hecho
  nuevo tipo `both_lateral_non_angular_damage`. Sigue el patrón de
  `decide_from_daa_matrix` en `backend/src/domain/rules/cide_matrix.py` (excepciones
  estructuradas en el artefacto, nunca en código) más que el `applies_when` simple
  de las demás reglas de maniobra.

### 3.2 Ingesta y perfiles (spec sección 6, anexo stack)

- pypdf + Docling: **ambos publicados y verificados** para el documento oficial.
- Densa + BM25 español + fusión RRF nativa de Qdrant: **implementado de verdad**
  (`backend/src/infrastructure/adapters/outbound/retriever/qdrant_retriever.py`),
  no es un placeholder.
- **Reranker: sólo declarado, sin implementación.** `profiles.py` tiene
  `reranker: Literal["none", "openai"] = "none"` pero no existe ningún adaptador que
  reordene resultados — el enum existe, la lógica no. Si vas a comparar chunking o
  recuperación como pide la spec (sección 3, "no se implementarán todas las
  combinaciones cartesianas, pero sí candidatos y controles"), esto es parte de lo
  que falta para que esa comparación tenga sentido completo.
- **Visión: sólo declarada, sin implementación.** Mismo patrón:
  `vision: Literal["none", "openai-responses"] = "none"` en `profiles.py`, ningún
  adaptador OpenAI-vision real. La spec la trata como "canal de evidencia
  identificado" para tablas/imágenes (matriz pág. 101, DAA escaneada pág. 32) — hoy
  ese canal no existe en absoluto, más allá del campo de configuración.
- Índice `structured` (Docling) construido pero **no activo** en la demo — la spec
  exige elegir por evaluación, no por disponibilidad, así que esto se resuelve solo
  cuando el bucle de la sección 2 produzca una comparación baseline-vs-structured
  real.

### 3.3 API y contratos HTTP (anexo API y experiencia)

Todos los endpoints de la tabla de la spec existen y responden:
`POST /api/v1/queries/resolve` (vía el envelope unificado `POST /api/v1/queries`),
`POST /api/v1/questions/answer`, `POST /api/v1/claims/analyze`, `GET /api/v1/manual`,
`GET /api/v1/manual/pdf`, `GET /api/v1/manual/evidence/{evidence_id}`,
`GET /api/v1/demo/cases`, `GET /health/live`, `GET /health/ready`. SSE con los cuatro
eventos (`started`/`stage`/`completed`/`failed`) implementado en
`backend/src/infrastructure/adapters/inbound/api/routes/queries.py`. Esta parte de
la spec está funcionalmente completa — no es donde hay que invertir tiempo.

### 3.4 Golden set y evaluación (spec de golden set, secciones 1-6)

- **Cobertura de familias incompleta** incluso tras fusionar los 110 (ver sección 1
  de este documento): falta inglés, falta `adversarial` (hechos inventados, citas
  incorrectas, instrucciones maliciosas insertadas en el contexto — sección 2.2 de
  la spec, "casos difíciles para la seguridad"), falta separar reserva.
- **Sin holdout.** Bloqueante para poder afirmar generalización según la spec — ver
  sección 2 de este documento.
- **Runner de experimentos incompleto**: sólo preguntas, no siniestros ni router —
  ver sección 2.
- **Casi ninguna métrica de la sección 3 de la spec está implementada** — ver
  sección 2. Esta es, con diferencia, la brecha más grande entre la spec y el
  código: la spec dedica una sección entera (8 dimensiones, ~20 métricas) a esto y
  hoy hay una sola métrica (F1 factual) con código real.
- **Sin calibración de jueces** (spec sección 4): ningún juez LLM se ha verificado
  contra un conjunto de errores conocidos antes de usarse.
- **Sin ninguna corrida ejecutada**: `data/evaluation/results/` no existe.

### 3.5 Frontend y experiencia

Verificado en sesiones anteriores (visor PDF con resaltado sólo con coordenadas
verificadas y fallback honesto a página completa, accesibilidad por teclado, modo
Automático con corrección visible, enlace "Ver en Langfuse", estados no dependientes
sólo de color) — esta parte cumple razonablemente la spec. Si durante el bucle de
evaluación detectas algo roto aquí, arréglalo, pero no es donde se concentran los
huecos grandes.

### 3.6 Operación (spec sección 11)

Healthcheck separado de llamadas pagadas (`/health/live` vs `/health/ready`),
secretos fuera de Git (`.env` gitignored), servicios sólo en localhost — cumplido.
No verificado a fondo en esta auditoría: que los logs realmente eviten datos
sensibles por defecto en todos los adaptadores; si tocas logging durante la noche,
revísalo de paso.

---

## 4. Verificación mínima antes de dar cualquier cosa por terminada

```bash
cd backend && uv run pytest -q                      # todos verdes, 0 nuevos fallos
cd .. && make lint-backend && make typecheck-backend && make check-openapi
make check-frontend                                  # si tocaste frontend

# backend real levantado, y una pasada de regresión contra el golden actual:
make serve-backend &   # espera ~9s a que /health/ready responda
python3 - <<'PY'
import json, urllib.request
cases = json.loads(urllib.request.urlopen("http://127.0.0.1:8000/api/v1/demo/cases").read())
golden = {json.loads(l)["metadata"]["case_id"]: json.loads(l)
          for l in open("data/evaluation/golden/development.jsonl", encoding="utf-8") if l.strip()}
for c in cases:
    body = json.dumps({"text": c["text"], "language": "es", "mode": "auto"}).encode()
    req = urllib.request.Request("http://127.0.0.1:8000/api/v1/queries", body, {"Content-Type": "application/json"})
    env = json.loads(urllib.request.urlopen(req, timeout=180).read())
    r = env.get("result") or {}
    exp = golden[c["case_id"]]["expected_output"]["decisions"]
    print(c["case_id"], "->", r.get("kind"), r.get("decision") or r.get("status"))
PY
```
