# Handoff — golden set sintético (100 casos) + huecos restantes

Prompt autocontenido para continuar el trabajo. Pégalo entero en una sesión nueva.

---

## Contexto del proyecto

`prueba-allianz` es un asistente RAG local sobre el manual CIDE/ASCIDE/CICOS (111
páginas, SHA-256 `b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344`,
edición de noviembre de 2004). Repo en `/Users/aoc/proyectos/prueba-allianz`, rama
`main`, se trabaja y se sube **directo a main** (sin PR) tras verificar los gates.
Backend Python/FastAPI/LangGraph en `backend/`, frontend React en `frontend/`.
Arranque: `make local-services-up` (Qdrant/Langfuse/Postgres/Redis/ClickHouse/MinIO),
luego `make serve-backend` y `make serve-frontend`.

Punto de entrada de estado: **`docs/ESTADO.md`** — léelo primero, y verifica sus
afirmaciones contra el código, no las des por buenas: el propio documento advierte
que una sesión anterior lo dejó con referencias muertas una vez.

Disciplina de este repo (documentada y aplicada en los últimos commits, revísalos con
`git log --oneline -15` para ver el estilo):

- TDD real: test en rojo antes que la implementación, no al revés.
- Nunca fingir cobertura. Una regla sin evidencia verificable se declara
  `insufficient_data`, nunca se adivina. Ver `backend/src/domain/rules/ruleset.py`.
- **Verificar con el modelo real** (`make serve-backend` levantado, llamadas HTTP de
  verdad), no sólo con dobles de test — los LLM tienen variabilidad; repite 3-4 veces
  antes de descartar algo como "arreglado" o etiquetarlo como "regresión".
- Antes de cada commit: `cd backend && uv run pytest -q`, luego desde la raíz
  `make lint-backend`, `make typecheck-backend`, `make check-openapi` — los cuatro en
  verde. Si tocas frontend, también `make check-frontend`.
- Commits con mensaje explicando el *porqué*, no sólo el qué. `git push origin main`
  después de verificar.
- `git fetch origin` antes de tocar nada: puede haber commits de otras sesiones en
  paralelo (ha pasado ya dos veces en este proyecto).

---

## Trabajo en curso que tienes que reconocer y continuar (NO empezar de cero)

Otra sesión ha generado **100 casos sintéticos** para el golden set, siguiendo el
patrón de los casos de referencia existentes, con su propia revisión adversarial.
Está todo sin comitear (`git status` lo mostrará como `??`):

- `data/evaluation/golden/_drafts/` — el pipeline de generación: `SPECIALIST_SPEC.md`
  (la spec que se usó), `batch_s1..s5.jsonl`/`.md` y `gen_bloque_a/b/c.py` (más bloques
  de generación). Son los materiales de trabajo, no el entregable final.
- `data/evaluation/golden/synthetic-expansion-2026-09-02/` — una release ya congelada
  con `manifest.json` (100 items, 50 question / 50 claim, `case_id` de
  `consulta-synth-01-...` a `siniestro-synth-52-...`), `items.jsonl` y `schema.json`.

**Esto NO está fusionado en `data/evaluation/golden/development.jsonl`**, que sigue
con los 10 casos que ya había (5 del enunciado + 5 en castellano, release
`v2-es-2026-09-02`, ya en `main`).

**Verificado ahora mismo**: `items.jsonl` de esa carpeta **falla `allianz golden
validate` con 5 errores de schema**. Reprodúcelo así:

```bash
mkdir -p /tmp/golden_check
cp data/evaluation/golden/synthetic-expansion-2026-09-02/items.jsonl /tmp/golden_check/development.jsonl
cd backend && uv run allianz golden validate --golden-root /tmp/golden_check --evidence-root ../data/extractions
rm -rf /tmp/golden_check
```

Los 5 casos con error (identificados por `case_id`):

1. `consulta-synth-09-colision-directa-definicion` — `evidence_requirements` con un
   `all_of` que repite un evidence_id (deben ser únicos).
2. `siniestro-synth-05-rotonda-partida` — `metadata.provenance.source_ids` repite un
   valor.
3. `consulta-synth-16-limite-perdida-total` — mismo problema de duplicados en
   `evidence_requirements`.
4. `consulta-synth-40-restos-fuera-perdida-total` — `provenance.source_ids` repetido.
5. `consulta-synth-42-pupilaje-baja-fuera` — `alternative_id: "alt-cobertura-póliza"`
   usa un carácter (`ó`) que el patrón de identificador no admite (sólo
   `[A-Za-z0-9._:-]`).

### Qué hacer con esto

1. Arregla los 5 errores (quita duplicados, renombra el `alternative_id` a algo como
   `alt-cobertura-poliza`). Revalida hasta que dé `errors: []` con `item_count: 100`.
2. **Antes de fusionar, haz lo mismo que se hizo con los 10 casos ya en `main`**: una
   revisión adversarial independiente (subagente con contexto limpio, sin ver el
   trabajo del generador) que verifique citas contra el manual página a página, busque
   requisitos sin evidencia real, `forbidden_facts` que falten, y decisiones
   demasiado confiadas. El patrón exacto (briefing + subagente + adjudicación) está en
   el historial de esta sesión — si no tienes ese contexto, al menos haz una pasada
   propia rigurosa: no fusiones 100 casos sin haberlos leído.
3. Fusiona con `data/evaluation/golden/development.jsonl` (110 casos en total),
   `allianz golden validate`, `allianz golden freeze --release <fecha>-100-casos`,
   `allianz golden publish` (necesita Langfuse arriba con las claves en `.env`).
4. Actualiza `docs/ESTADO.md` y `docs/entrega/arquitectura.md` con el recuento real.
5. Comitea y sube.

**No borres `_drafts/` ni `synthetic-expansion-2026-09-02/` sin confirmarlo** — son
trabajo de otra sesión, no tuyo.

---

## Lo que se hizo en la sesión inmediatamente anterior (ya en `main`)

Verifícalo con `git log --oneline -6` (deberías ver, de más reciente a más antiguo):
`73f9c47`, `1222b17`, `d72f721`, `752a71d`, `db4dab1`... El trabajo:

- **13 de las 14 reglas del ruleset firmado (`data/rules/ruleset.v1.json`) están
  conectadas** con condición verificable (`applies_when`) y su convenio leído del
  artefacto (nunca inferido del `kind`, que mezcla ASCIDE y CIDE). Incluye la tabla de
  culpabilidad CIDE (18×18, con sus 4 observaciones/excepciones estructuradas).
- Se corrigió que la entrevista del LLM se abriera en casos ya excluidos por reglas
  deterministas (`not_applicable` no puede quedar `conditional`: nuevo invariante en
  `backend/src/domain/models/decision.py`).
- Se corrigieron dos confusiones sistemáticas del planificador de entrevista LLM:
  trataba "el relato dice que un dato no consta" como una pregunta pendiente, y
  "disparidad de versiones" como caso irresoluble — ambas rompían justo las normas
  subsidiarias que existen para esos supuestos.
- Todo verificado con el modelo real (backend levantado, llamadas HTTP reales,
  repetidas 3-4 veces), no sólo con dobles de test.

---

## Lo que queda pendiente, por orden de impacto

1. **`ascide-b11-roundabout`** es la única regla de maniobra sin conectar. A
   diferencia de las demás, su excepción tiene un **resultado alternativo** (no una
   simple retirada): "culpable quien accede a la rotonda, salvo que ambos tengan
   daños laterales no angulares, en cuyo caso culpable el de daños en el lateral
   derecho" (manual, pág. 75). El motor de reglas actual (`evaluate_ruleset`) sólo
   soporta un `applies_when` con un outcome fijo por regla — para modelar esto sin
   inventar nada necesitas **dos reglas** en el artefacto, mutuamente excluyentes por
   un hecho adicional (p. ej. `both_lateral_non_angular_damage`), siguiendo el mismo
   patrón de `decide_from_daa_matrix` (`backend/src/domain/rules/cide_matrix.py`) más
   que el patrón simple de `applies_when` de b.5/b.6/b.9/b.10. Lee primero cómo se
   resolvió la matriz para no reinventar el enfoque.

2. **La evaluación no se ha ejecutado nunca.** `run_experiment` de Langfuse está
   cableado (`backend/src/infrastructure/adapters/outbound/evaluation/`) pero no hay
   `data/evaluation/results/`, ni holdout, ni métricas de recuperación/router/citas/
   abstención, ni calibración de jueces. Con el golden ampliado a ~110 casos (tras el
   punto de arriba) esto por fin tiene sentido ejecutarlo. No hagas esto sin antes
   congelar development y separar un holdout real, tal como exige
   `docs/evaluation/2026-08-31-golden-set-y-metricas-rag.md`.

3. **Índice Docling publicado pero no activo en la demo.** Existe la extracción
   estructurada y un índice Qdrant `structured` construido, pero el perfil servido
   sigue siendo `baseline` (pypdf) porque no hay evaluación que justifique el cambio.
   No lo actives sin datos — es exactamente la disciplina que el proyecto pide.

4. **El golden set entero (10 + ~100 casos) sigue con revisión de IA, no de un
   experto humano del dominio.** Declarado explícitamente en `metadata.review` de
   cada caso; no lo ocultes ni lo llames "revisión experta" en la documentación.

5. **`docs/entrega/presentacion.pptx` tiene cambios locales sin comitear** (se abrió y
   guardó en LibreOffice en algún punto). Antes de tocarlo, decide con el usuario qué
   versión quiere conservar — no lo sobrescribas sin preguntar.

---

## Verificación mínima antes de dar nada por terminado

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
