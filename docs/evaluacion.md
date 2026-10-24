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

### Modelos configurados y resultados medidos

Los defaults OpenAI son `gpt-6.1-sol` para respuesta y extracción, y
`gpt-6-luna` como router de referencia; Jev es el router predeterminado con
umbral 0,4. La suite live de esta campaña usó `gpt-6-luna` para respuesta,
extracción y router OpenAI, por decisión del usuario. No se hizo ninguna llamada
real a GPT-6.1 Sol. Los IDs figuran en el
[catálogo oficial](https://developers.openai.com/api/docs/models).

**A/B end-to-end del router (24-10-2026).** Se repitió el modo `auto` con
110 casos en el mismo commit base, huella del código, perfil, prompts y firma
del alias activo de Qdrant; las dos corridas usaron Luna para respuesta y
extracción y concurrencia 2. Jev (`jev-latest`, umbral 0,4) acertó 97/110
(88,2 %); OpenAI Luna acertó 96/110 (87,3 %). Ambas terminaron 110/110 sin
errores técnicos. Jev supera el gate de exactitud por un caso. Los manifiestos
incluyen huella de código e identidad del índice activo; la comparación es
reproducible sobre esta versión del golden.

Artefactos locales ignorados por Git:
`data/evaluation/results/2026-10-24-final-jev-luna-all-modes-normalized/` y
`data/evaluation/results/2026-10-24-router-openai-luna-e2e-current/`.
Las comparaciones del 22-10 (Jev 97/110, OpenAI 95/110) se conservan como
históricas: sus manifiestos no incluyen huella de código ni firma del índice
activo, por lo que no se usan como gate de esta versión. El barrido de umbral
0,4/0,6/0,8 también es histórico; debe repetirse si cambia el router o el
golden. No se guardan credenciales en los manifiestos.

**Red-team actual (24-10-2026; 30 casos, 27 ataques y 3 controles).** Con
router Jev y `guard=off` se registró 1/27 ataques exitosos (3,7 %) y 0/3
sobre-rechazos. Con guard Jev a 0,9/0,95 se obtuvo 0/27 y 0/3. La comprobación
adicional con router OpenAI Luna y guard Jev también dio 0/27 y 0/3. Por tanto,
Jev supera el gate frente a `off` con el router Jev y no añade sobre-rechazo
cuando se usa el router OpenAI. Las campañas de 24-10 tienen huella de código,
configuración y firma del índice activo.

Resultados locales: `2026-10-24-redteam-jev-router-guard-off-current/`,
`2026-10-24-redteam-jev-router-jev-guard-current/` y
`2026-10-24-redteam-openai-router-jev-guard-current/` bajo
`data/evaluation/results/`. Las carpetas del 22-10 son históricas; sus
manifiestos no registran la identidad del índice activo.

El uso de tokens observado queda en los manifiestos y salidas por caso. No se
infiere ahorro monetario sin tarifas TypeSafe/Langfuse configuradas. El juez Jev
sigue opt-in y sus puntuaciones exploratorias hasta medir acuerdo con etiquetas
humanas. OpenAI conserva `store=False`; esto no desactiva por sí solo los logs de
abuso, que pueden incluir contenido hasta 30 días por defecto. No se enviaron
relatos reales con datos personales.

## Métricas

Los evaluadores deterministas
(`infrastructure/adapters/outbound/evaluation/domain_evaluators.py` y
`evidence_evaluators.py`) no necesitan un juez LLM y son reproducibles:

| Métrica | Qué mide |
|---|---|
| `answer_status_accuracy` | acierto del estado de la respuesta documental |
| `applicability_accuracy` | acierto de aplicabilidad del Convenio |
| `convention_accuracy` | acierto del convenio (CIDE / ASCIDE) |
| `claim_decision_accuracy` | acierto de la decisión del siniestro |
| `citation_id_validity` | proporción de IDs citados presentes en el catálogo de evidencia permitido para el caso; una cita obligatoria ausente puntúa 0 |
| `evidence_bundle_coverage` | proporción de requisitos del golden cubiertos por un paquete AND completo; cualquier paquete OR completo satisface el requisito |
| `over_resolution_rate_against_reference` | fracción de decisiones `resolved` frente a una referencia que exige abstenerse |
| `resolution_support_rate` | proporción de resoluciones con actor, regla `matched` y evidencia estructurados; queda como missing si el actor no está expuesto por el envelope |
| `abstention_metrics` | acierto al abstenerse cuando corresponde |
| `router_confusion_matrix` | acierto y confusiones del enrutado automático |
| `router_accuracy_all_labeled` | exactitud sobre todos los casos auto con etiqueta; errores y rutas ausentes cuentan como incorrectos. La matriz de confusión sigue mostrando sólo rutas observadas. |

Cada métrica numérica se guarda con `n_total`, `n_applicable`, `n_scored`,
`n_missing`, `n_error` y `n_not_applicable`. Debe cumplirse
`n_total = n_scored + n_missing + n_error + n_not_applicable`; los errores y
los campos ausentes no se convierten en ceros ni desaparecen del denominador.

## Métricas con juez (opcionales)

`run_baseline.py --judge jev` (requiere `TYPESAFE_API_KEY`) añade, sólo al modo
`question`, tres medidas que las deterministas no cubren. Cada una es una
probabilidad de un modelo de decisiones, no una verdad:

| Métrica | Qué mide |
|---|---|
| `jev_context_relevance` / `jev_context_precision` | media de la probabilidad de que cada página entregada al modelo sirva para la pregunta, y proporción de páginas con probabilidad ≥ 0,5 |
| `jev_groundedness` / `jev_groundedness_min` | probabilidad media (y mínima) de que cada bloque de la respuesta esté sostenido por las páginas que cita |

Los pasajes se leen de `GET /api/v1/manual/evidence/{id}`. Un fallo del juez se
anota como `jev_judge_error` y cuenta en `n_error` para esas métricas, sin
invalidar las métricas deterministas del caso. **No citar estas cifras sin
calibrarlas** contra etiquetas humanas de una muestra y reportar el acuerdo.

## El runner

```bash
make run-baseline ARGS="--output data/evaluation/results/<fecha>-<etiqueta> \
    --label <etiqueta> --concurrency 4"
```

Arranca el runner con los mismos `.env` y `ops/local.env` que `make serve-backend`.
Para un A/B o una campaña con parámetros distintos, pasa las mismas asignaciones
en `LOCAL_ENV` tanto al backend como al runner, por ejemplo
`make run-baseline LOCAL_ENV="ALLIANZ_ROUTER_BACKEND=jev" ARGS="..."`. El
manifiesto registra esa fuente de configuración junto a modelos y umbrales del
router y del guardarraíl.
Ejecuta el golden contra el backend en marcha, en sus tres modos, y escribe:

```
<output>/
├── manifest.json   dataset, commit, modelos y ventana temporal
├── metrics.json    agregados por dimensión
├── summary.txt     tabla legible
└── per-case/       un JSON por caso, con los tres modos y sus métricas
```

No sobrescribe corridas: si la carpeta de salida contiene datos, falla salvo que
se use `--resume`. La reanudación exige que coincidan commit, golden, modelos y
configuración, conserva los modos completos y vuelve a intentar los fallidos.
Los errores y casos ausentes se cuentan por separado. El runner es local y no
publica nada en Langfuse, pero cada caso conserva su `trace_id` y su enlace.

## Resultados medidos

### Corrida actual (24-10-2026)

Golden de 110 casos × tres modos: 330/330 resultados completos, cero errores
técnicos, 1092,4 s. Respuesta y extracción usaron `gpt-6-luna`; router y
guardarraíl usaron Jev (`jev-latest`, 0,4; umbrales 0,9/0,95). El manifiesto
fija el commit base `99ff2f48`, fingerprint del árbol ejecutado
`3c074a5069b273f0…`, hash del manual y firma del alias activo
`allianz-manual-active` (118 puntos).

| Modo | Métrica | Valor | n_scored | n_missing | n_error | n_not_applicable |
|---|---|---:|---:|---:|---:|---:|
| question | `answer_status_accuracy` | 0,566 | 53 | 0 | 0 | 57 |
| question | `citation_id_validity` | 0,385 | 110 | 0 | 0 | 0 |
| question | `evidence_bundle_coverage` | 0,483 | 110 | 0 | 0 | 0 |
| claim | `applicability_accuracy` | 0,500 | 6 | 103 | 0 | 1 |
| claim | `convention_accuracy` | 0,000 | 2 | 103 | 0 | 5 |
| claim | `claim_decision_accuracy` | 0,500 | 6 | 103 | 0 | 1 |
| claim | `citation_id_validity` | 0,036 | 110 | 0 | 0 | 0 |
| claim | `evidence_bundle_coverage` | 0,015 | 110 | 0 | 0 | 0 |
| auto | `router_match` (Jev, 0,4) | 0,882 | 110 | 0 | 0 | 0 |

El modo `claim` pidió aclaración en 103/110 casos. Los datos más solicitados
fueron ubicación dentro del ámbito (102 casos), estacionamiento habitual en
España (103), matriculación española (101) y aseguradora adherida (100); además,
faltó el número de vehículos en 50 y confirmar colisión directa en 66. Las
aclaraciones figuran como faltantes/no puntuables, no como errores técnicos.
La validez y cobertura de citas puntúan cero cuando no se entrega una cita. La
accuracy de decisión 0,500 sólo se calculó sobre seis casos y **no demuestra
calidad suficiente para resolver siniestros**. Antes de presentar el sistema
como resolutor listo, hay que adjudicar la política de ámbito y completar el
golden con los hechos necesarios, o mejorar la extracción sin convertir hechos
desconocidos en verdaderos.

En el A/B actual del router, Jev acertó 97/110 (88,2 %) y OpenAI Luna 96/110
(87,3 %), ambos sin errores. Los manifiestos comparten commit base, fingerprint,
hash del manual y firma del índice. Artefactos locales:
`data/evaluation/results/2026-10-24-final-jev-luna-all-modes-normalized/` y
`data/evaluation/results/2026-10-24-router-openai-luna-e2e-current/`.

Las campañas anteriores se ejecutaron antes de añadir la compatibilidad local
de `LANGFUSE_BASE_URL=http://host.docker.internal:3000` para el contenedor. La
corrida host utilizaba `http://127.0.0.1:3000`; la diferencia sólo afecta a la
composición de entorno Docker. El fingerprint final del servidor, visible en
`/health/config`, quedó en `b7896fb27b94e334…` después de ese ajuste.

La corrida de 24-10 sustituye el estado pendiente anterior. La corrida de
`2026-09-03` que sigue se conserva como referencia histórica y no recalculable.

Corrida completa sobre los 110 casos × 3 modos, `2026-09-03`, commit
`3b452ee`, modelo `gpt-5.6-luna` en las tres etapas para acotar el coste,
1379,9 s, 329 de 330 ejecuciones sin error:

Estos valores son una transcripción histórica. En este checkout no están los
`per-case/*.json` originales ni el manifiesto de esa corrida, por lo que no se
pueden recalcular con los denominadores y métricas AND/OR actuales. No
representan una nueva medición del código actual; la tabla se mantiene sólo
como referencia histórica hasta repetir la corrida y guardar sus artefactos
completos.

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
