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

### Modelos configurados

Los defaults versionados son `gpt-6.1-sol` para respuesta y extracción, Jev
(`jev-latest`) para router y guard, y `gpt-6-luna` como router OpenAI de
referencia. Los IDs OpenAI figuran en el
[catálogo oficial](https://developers.openai.com/api/docs/models). Según la
instrucción del usuario, **todas las llamadas OpenAI de esta campaña usaron
Luna**, incluida la extracción downstream; Sol no se probó. Los defaults de
respuesta/extracción permanecen en Sol y su evaluación sigue pendiente.

En `auto`, el envelope y los registros por caso conservan proveedor/modelo del
router y sus tokens de entrada/salida cuando el proveedor los devuelve. Así se
compara el uso observado del router Jev y OpenAI sin inventar tokens ausentes.
La estimación orientativa con tarifas públicas, separada del gasto facturado,
se documenta en el A/B siguiente.

El humo real de Jev (una llamada sintética, 22-10-2026) respondió `noul` y
`choice` con `jev-1.14.0`, probabilidades válidas y uso de tokens. No se
enviaron relatos reales ni datos personales.

### A/B del router Jev

La repetición final del modo `auto` se ejecutó en el commit
`75da6320266f857e717fa9b846c44baaa0f4c746`, sobre los mismos 110 casos, el
golden SHA-256 `837dfb6da86bcdf6cb7e2a1477623141b83c021f5c697910da5dfa1af074d874`
y concurrencia 4. `/health/config` confirmó antes de cada campaña los modelos,
el router y sus umbrales: Jev `0,4` o OpenAI `gpt-6-luna` como router, Jev como
guard y Luna para respuesta y extracción. Los manifiestos registraron el commit
del runner y el hash configurado del manual; aquella versión del endpoint no
verificaba el build del servidor ni el destino/firma del alias activo de Qdrant.
La comprobación reforzada de esos datos se añadió después y se verificó en la
validación final descrita en `docs/entrega/validacion-pendiente.md`. Todas
terminaron con los
110 casos completos y cero errores sin resolver. Cada campaña tuvo un error
HTTP transitorio en su primera pasada; `--resume` reintentó sólo ese caso.

| Router | Acierto end-to-end | Errores finales | Tokens medios entrada/salida del router | Duración aproximada acumulada |
|---|---:|---:|---:|---:|
| OpenAI `gpt-6-luna` | 94/110 (0,855) | 0 | 332,782 / 75,309 | 358,4 s |
| Jev `jev-latest`, `0,4` | 97/110 (0,882) | 0 | 476,491 / 41,027 | 297,3 s |

La duración acumulada suma el primer intento parcial y el reintento. Los
manifiestos nativos creados antes de corregir la acumulación automática sólo
conservan en `duration_s` el tiempo del reintento; las aproximaciones de la
tabla proceden de las dos salidas del runner. Los artefactos `per-case` sí
contienen los 110 casos de cada campaña. El runner acumula segmentos de tiempo
en nuevas reanudaciones desde el commit `16e2c82`.

Matrices (`claim → claim/clarification/question; question →
claim/clarification/question`): OpenAI `54/0/3; 13/0/40`; Jev `45/2/10;
1/0/52`. Esta puerta usa `router_end_to_end_accuracy_all_labeled`: cuenta
rutas observadas correctas y penaliza rutas ausentes o fallos técnicos de
cualquier etapa del modo `auto`. Mide disponibilidad y acierto del flujo
automático completo; no aísla el clasificador. La matriz sólo incorpora rutas
observadas.

El barrido exploratorio anterior comparó Jev a `0,4`, `0,6` y `0,8`; en esa
pasada `0,6` obtuvo 92/110 y `0,8` 83/110. El golden sirvió tanto para elegir
umbral como para medirlo, por lo que no equivale a un holdout independiente.
La repetición final obtuvo 97/110 para Jev `0,4` frente a 94/110 para Luna;
Jev queda como estándar, con la limitación de que el resultado es de un golden
sintético y no garantiza la misma ventaja en producción.

Los tokens anteriores son sólo del router; los tokenizadores de proveedores
son distintos. Con las tarifas públicas consultadas el 22-10-2026 (Jev: `$0.042`
por millón de tokens de entrada y salida gratuita; Luna Standard: `$0.10` de
entrada y `$0.50` de salida), el coste de lista estimado por decisión es
`$0.000020` para Jev `0,4` y `$0.000071` para Luna, aproximadamente **72 % menos
para el router**. No es una factura observada y no estima el coste completo del
flujo de respuesta/extracción. Fuentes: [TypeSafe](https://typesafe.ai/) y
[OpenAI Pricing](https://developers.openai.com/api/docs/pricing).

### Red-team del guardarraíl

Con el commit `75da6320266f857e717fa9b846c44baaa0f4c746`, los mismos 30 casos (27 ataques, 3 controles benignos),
el router Jev `0,4` y concurrencia 4, se ejecutó primero `off` y luego el guard
Jev con umbrales de inyección `0,9` y fuera de tema `0,95`. En ambos: tasa de
éxito del atacante `0/27`; sobre-rechazo `0/3`. Las diez categorías (inyección
directa, filtrado de prompt, delimitadores, citas falsas, fuera de ámbito,
anulación de reglas, ofuscación, exfiltración, inyección al router y robustez)
registraron cero ataques exitosos. El guard Jev pasa su puerta y queda como
default. La muestra de controles benignos es pequeña; el resultado no demuestra
cero sobre-rechazo en producción.

TypeSafe declara que no entrena con solicitudes/respuestas, pero su retención
depende del acuerdo, los datos y cualquier arreglo ZDR; por eso sólo se usaron
entradas sintéticas. Revisar el
[tratamiento y retención de datos](https://help.typesafe.ai/articles/5974925716-how-is-submitted-data-used-or-retained)
antes de enviar relatos reales.

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
| `router_end_to_end_accuracy_all_labeled` | acierto del flujo `auto` completo sobre todos los casos etiquetados; rutas ausentes y errores técnicos de cualquier etapa cuentan como fallos. No es una métrica aislada del clasificador. La matriz de confusión sólo muestra rutas observadas. |

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
