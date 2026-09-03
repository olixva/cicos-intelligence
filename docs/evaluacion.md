# Evaluación

Cómo se mide el sistema: qué conjunto de referencia se usa, con qué métricas,
y qué salió al ejecutarlo.

## El golden set

`data/evaluation/golden/development.jsonl` — **110 casos**, congelados como la
release `synthetic-expansion-110-2026-09-03` bajo
`data/evaluation/golden/releases/`.

| | |
|---|---|
| Intención esperada | 57 `claim` · 53 `question` |
| Idioma | 105 en español · 5 en inglés |
| Procedencia | 7 del enunciado · 102 derivados del manual · 1 adversarial |
| Esquema | v1.0.0, SHA `3f70aa5a…4a36` |
| Contenido | SHA `73d0981b…3dc4` |

Incluye los **cinco siniestros del enunciado** (`accident-01-rear-end` …
`accident-05-alcohol-injury`), sus variantes en español, y casos sintéticos
que cubren consultas documentales, siniestros resolubles por norma
subsidiaria, siniestros resolubles por la tabla CIDE, casos fuera del ámbito
del Convenio y casos adversariales pensados para provocar una respuesta
inventada.

### Esquema de cada caso

```
input           text, language, clarifications
expected_output reference, decisiones esperadas (applicability, convention,
                claim_decision), requisitos verificables, alternativas
                aceptables, prohibiciones específicas y paquetes de evidencia
                AND/OR citando páginas reales del manual
metadata        case_id, family_id, partition, review_status, provenance,
                language, expected_intent, review
```

Los requisitos de evidencia son paquetes `all_of` / `any_of` de
`evidence_id` reales: un caso no se da por bueno porque el texto suene bien,
sino porque cita las páginas que lo sostienen.

### Revisión

Los casos pasaron por tres pasos de revisión encadenados —resolución
independiente, revisión adversarial y adjudicación— y cada uno queda registrado
en `metadata.review` con su nota de adjudicación. **La revisión es de IA, no
de un experto humano del dominio**: el conjunto es una referencia sintética
auditada contra el manual, y así está declarado en cada caso.

### Herramientas

```bash
allianz golden validate                       # esquema, evidencia y etiquetas
allianz golden freeze --dataset D --release R # congela una release con hashes
allianz golden publish --release R            # publica el dataset en Langfuse
```

`validate` comprueba que cada `evidence_id` citado exista realmente en las
publicaciones de ingesta. Los items marcados como `technical_fixture` se
rechazan por defecto en cualquier release real; sólo se admiten con un flag
explícito para el humo de CI.

## Métricas

Los evaluadores deterministas
(`infrastructure/adapters/outbound/evaluation/domain_evaluators.py`) no
necesitan un juez LLM y son reproducibles:

| Métrica | Qué mide |
|---|---|
| `answer_status_accuracy` | acierto del estado de la respuesta documental |
| `applicability_accuracy` | acierto de aplicabilidad del Convenio |
| `convention_accuracy` | acierto del convenio (CIDE / ASCIDE) |
| `claim_decision_accuracy` | acierto de la decisión del siniestro |
| `evidence_validity` | proporción de citas que son evidencia válida y esperada |
| `unjustified_resolution_rate` | resoluciones sin una regla que las sostenga |
| `abstention_metrics` | acierto al abstenerse cuando corresponde |
| `router_confusion_matrix` | acierto y confusiones del enrutado automático |

## El runner

```bash
cd backend && uv run --no-sync python scripts/run_baseline.py \
    --output ../data/evaluation/results/<fecha>-<etiqueta> \
    --label <etiqueta> --concurrency 4
```

Ejecuta el golden contra el backend en marcha, en sus tres modos, y escribe:

```
<output>/
├── manifest.json   dataset, commit, modelos y ventana temporal
├── metrics.json    agregados por dimensión
├── summary.txt     tabla legible
└── per-case/       un JSON por caso, con los tres modos y sus métricas
```

Es idempotente por construcción: si la carpeta de salida existe, falla con un
error claro en lugar de mezclar corridas. Los errores por caso no detienen el
bucle; se cuentan y se reportan. El runner es local y no publica nada en
Langfuse, pero cada caso conserva su `trace_id` y su enlace.

## Resultados medidos

Corrida completa sobre los 110 casos × 3 modos, `2026-09-03`, commit
`3b452ee`, modelo `gpt-5.6-luna` en las tres etapas para acotar el coste,
1379,9 s, 329 de 330 ejecuciones sin error:

| Modo | Métrica | Valor | n |
|---|---|---|---|
| question | `answer_status_accuracy` | 0,585 | 110 |
| question | `evidence_validity` | 0,370 | 110 |
| claim | `applicability_accuracy` | 0,829 | 39 |
| claim | `convention_accuracy` | 0,120 | 39 |
| claim | `claim_decision_accuracy` | 0,314 | 39 |
| claim | `evidence_validity` | 0,526 | 39 |
| auto | `router_match` | 0,964 | 110 |

Matriz de confusión del router (110 casos): 55 `claim→claim`, 51
`question→question`, 2 `claim→question`, 2 `question→claim`.

### Qué dicen estos números

**El enrutado funciona.** 0,964 de acierto con cuatro confusiones sobre 110, y
ninguna de ellas cambia la naturaleza de la respuesta hasta el punto de
inventar una.

**La aplicabilidad funciona.** 0,829: la puerta de dos vehículos, colisión
directa, tercero identificado y colisión en cadena decide bien la mayoría de
los casos.

**La accuracy de convenio y decisión es engañosa a primera vista.** El
análisis de los desajustes mostró que, cuando el ruleset dispara, el resultado
suele ser correcto; el problema era que **no disparaba** en unos 19 de 25
desajustes. La causa concreta: las guardas negativas estaban modeladas como
`is_false` estricto —«dispara sólo si se constata el falso»— cuando la nota de
la regla decía «dispara salvo que se contradiga explícitamente». Eso se
corrigió introduciendo el operador `is_false_or_absent` y reescribiendo las
dos reglas afectadas (`ascide-b6-exit-from-parking` y `cide-door-opening`);
`is_false` estricto no cambió, y hay un test de regresión que lo fija. Los
números de la tabla son anteriores a esa corrección.

Un marco alternativo que se descartó al analizarlo: no es que el workflow deje
campos en `None` en vez de emitir `undetermined` explícito. El workflow **sí**
emite `undetermined`; era el ruleset el que no llegaba a disparar.

**La abstención se comporta.** `unjustified_resolution_rate` = 0: el sistema
no resolvió ningún caso sin una regla que lo sostuviera. Es la propiedad que
más importa en un dominio donde una atribución inventada tiene coste real.

## Trazas

Con Langfuse configurado, cada ejecución deja su traza (`question_workflow`,
`claim_workflow`, `OpenAI-generation`, `OpenAI-embedding`) bajo el proyecto
local, y la respuesta del API incluye el enlace directo. Los prompts de
generación y routing están versionados en Langfuse y se aprovisionan con
`make provision-prompts`.
