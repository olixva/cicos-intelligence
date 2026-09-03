# Reglas y decisión

El análisis de un siniestro no lo decide un modelo de lenguaje. El modelo
extrae hechos del relato y redacta la explicación; la decisión sale de
artefactos firmados que una persona puede leer y de un motor determinista que
los ejecuta.

## Los tres artefactos firmados

Viven versionados en `data/rules/` y se validan contra su JSON Schema al
cargarse. Todos llevan `attestation` obligatoria y el hash del documento del
que derivan; una carga con firma incompleta falla de forma ruidosa.

| Artefacto | Contenido |
|---|---|
| `ruleset.v1.json` | 14 reglas del Convenio, cada una con su evidencia y su revisor |
| `cide-matrix.v1.json` | tabla de culpabilidad CIDE 18×18 (324 celdas) + 4 observaciones impresas |
| `daa-circumstances.v1.json` | catálogo de las 18 casillas `A0`–`A17` del apartado 12 de la D.A.A. |

Los esquemas correspondientes (`ruleset.schema.json`,
`cide-matrix.schema.json`) están junto a ellos.

### El ruleset

Cada regla declara: `rule_id`, `kind`, descripción legible, `prerequisites`,
`outcome` (la consecuencia que su revisor firmó), `evidence_ids` (páginas del
manual), `reviewer_id`, opcionalmente `convention` y una condición
`applies_when`.

| `kind` | Reglas |
|---|---|
| `applicability` | `convention-scope`, `cide-requires-two-vehicles`, `cide-requires-direct-collision` |
| `third_party` | `third-vehicle-identified-excludes-convention` |
| `exception` | `chain-collision-excludes-convention`, `alcohol-does-not-exclude-convention` |
| `manoeuvre` | `ascide-b5-parked-vehicle`, `ascide-b6-exit-from-parking`, `ascide-b9-reverse-vs-rear-impact`, `ascide-b10-lane-change`, `ascide-b11-roundabout`, `ascide-traffic-light-amber`, `cide-door-opening` |
| `matrix_lookup` | `cide-matrix-lookup` |

El convenio (CIDE o ASCIDE) se lee del campo `convention` del artefacto, no se
deduce del `kind`: `cide-door-opening` es una regla de maniobra y es CIDE. Una
regla que no declara convenio resuelve **sin** nombrar ninguno en lugar de
suponerlo.

### El lenguaje de condiciones

`applies_when` usa un lenguaje cerrado y diminuto, evaluado en
`domain/rules/ruleset.py`. Existe precisamente para que la condición viva en
el artefacto que firma un revisor, y no en código que sólo lee un programador:

| Operador | Significado |
|---|---|
| `eq`, `ne` | igualdad / desigualdad textual |
| `gt`, `lt` | comparación numérica |
| `is_true`, `is_false` | el hecho consta y vale verdadero / falso |
| `is_false_or_absent` | el hecho vale falso **o** no consta |
| `all`, `any` | composición de ramas |

La distinción entre `is_false` y `is_false_or_absent` es la que separa dos
lecturas distintas de una nota del manual: «dispara sólo si se constata que
es falso» frente a «dispara salvo que se contradiga explícitamente». Los
campos guardados por `is_false_or_absent` quedan exentos del chequeo de hechos
faltantes; los guardados por `is_false` no.

Un operador desconocido es un error del artefacto, nunca una condición que se
ignora en silencio.

### Los nombres de los hechos salen del ruleset

`fact_names()` recorre las reglas y devuelve, en orden de artefacto, todos los
hechos que consultan. Ese es el listado exacto con el que se construye el
prompt del extractor. Así ninguna regla puede depender de un hecho que nadie
pidió nunca extraer — un fallo real que tuvo este sistema: la regla del
alcohol, cuya razón de ser es impedir una exclusión incorrecta, no podía
dispararse porque nada extraía `driver_under_influence`.

## La puerta de aplicabilidad

`domain/rules/applicability.py` implementa el filtro conservador previo, con
tres estados y sólo sobre hechos confirmados (`None` significa «no consta»):

- **`not_applicable`** si los vehículos son distintos de dos, si hay un tercer
  vehículo identificado, si es colisión en cadena, o si hay dos vehículos sin
  colisión directa.
- **`undetermined`** si falta confirmar el número de vehículos o la colisión
  directa. Devuelve la lista concreta de lo que hay que confirmar.
- **`applicable`** sólo cuando la puerta se satisface entera.

La evaluación exige `evidence_ids`: no se puede afirmar aplicabilidad sin
citar la página que la sostiene.

## La tabla de culpabilidad CIDE

La tabla de la página 101 cruza las circunstancias declaradas por cada parte
en el apartado 12 del parte amistoso europeo (D.A.A.). Está transcrita entera
—324 celdas— con doble transcripción independiente y adjudicación humana
firmada. No se autotranscribe desde las tablas de Docling: una tabla mal leída
que reparte responsabilidad no es un error tolerable.

`decide_from_daa_matrix` distingue cuatro resultados que la interfaz no puede
confundir:

| Resultado | Significado |
|---|---|
| `attributes` | la celda atribuye responsabilidad, citando la página |
| `no_attribution` | la celda es un «-»: la tabla **no atribuye nada** |
| `needs_exception_fact` | la celda lleva asterisco y falta el hecho decisorio de su observación |
| `exception_applies` | la observación se cumple y **retira** la atribución |

Las cuatro observaciones impresas bajo la tabla están declaradas de forma
estructurada en el artefacto (`applies_to`, `exception_fact`,
`exception_actor`, `liable_unless_exception`), nunca en código. Una celda con
asterisco sin observación anotada **no decide**.

La tabla sólo se consulta si las casillas vienen declaradas explícitamente:
ninguna descripción en prosa sustituye a un par `A1`/`B8` marcado. Y `A0` no
es una casilla real de la D.A.A., sino la convención interna de la matriz para
«sin circunstancia declarada»; el catálogo lo marca como tal.

## La entrevista

Cuando falta un dato decisorio, el grafo no adivina: se detiene con un
`interrupt` de LangGraph y pide exactamente lo que necesita. Un ejemplo real
del flujo: un par `A2 + B4` resuelve «culpable B, salvo que el A abra la
puerta»; sin el hecho de la puerta, el sistema pregunta por el texto de esa
observación. Si responde «B abrió la puerta», resuelve a B; si responde «A
abrió la puerta», la excepción retira la atribución y el resultado queda
`undetermined` sin inventar quién responde.

La respuesta llega como `clarifications` y el grafo se reanuda desde su
checkpoint, sin repetir preguntas ya contestadas.

Dos patrones que el planificador de entrevista tuvo que aprender a distinguir,
porque rompían reglas enteras:

- «el relato declara que un dato **no consta**» no es lo mismo que «hay que
  preguntarlo» — la condición de activación de `cide-door-opening` es
  precisamente esa ausencia;
- «hay disparidad de versiones» no es «el caso es irresoluble» — `ascide-b9`,
  `b10` y `b11` existen justamente para resolver esa disparidad.

## Qué produce el análisis

```
applicability : applicable | not_applicable | undetermined
convention    : CIDE | ASCIDE | null
decision      : resolved | conditional | undetermined | not_assessed
```

Acompañados de los hechos extraídos con su origen, las contradicciones entre
versiones (que se preservan, no se resuelven a la fuerza), las condiciones
pendientes, la información que falta, los bloques de evidencia y
`rules_evaluated`.

`rules_evaluated` es la traza de auditoría: **cada regla que realmente
corrió**, con las entradas que vio, su resultado (`matched`, `not_matched`,
`insufficient_data`) y las páginas del manual detrás. Nunca un marcador de
posición. Una regla de exclusión que no se activa se redacta como «no se
activa con …», no como «no se cumple»: son cosas distintas y la segunda
redacción llegó a leerse como lo contrario de lo que decía.

Un `decision: resolved` exige una regla que haya casado con su evidencia. Si
casan varias reglas de maniobra en conflicto, el resultado se queda en
`undetermined` en lugar de elegir una.

## Herramientas de verificación

```bash
allianz rules validate --matrix data/rules/cide-matrix.v1.json \
                       --ruleset data/rules/ruleset.v1.json
allianz rules compare-transcriptions IZQUIERDA DERECHA
```

`validate` comprueba el esquema, la firma, que el hash del documento coincida
y que toda la evidencia citada exista realmente en las publicaciones de
ingesta. `compare-transcriptions` informa sólo de las diferencias entre dos
transcripciones independientes de la matriz.

## Límites declarados

Son límites de la fuente y del alcance, no del sistema:

- **El manual es la edición de noviembre de 2004.** Es la fuente evaluada; no
  es derecho vigente ni una decisión operativa de Allianz.
- **El manual no define qué maniobra representa cada casilla `A0`–`A17`.** Son
  casillas de un formulario externo al manual, el parte amistoso europeo.
  Ningún catálogo que las traduzca puede citar el manual como fuente; por eso
  `daa-circumstances.v1.json` declara su procedencia externa.
- **El alcance del Convenio no es responsabilidad civil general.** El sistema
  evalúa aplicabilidad y criterios convencionales; no emite una opinión
  general de responsabilidad.
- **La alcoholemia no excluye el Convenio** (pág. 9 del manual). Lo penal y
  los daños personales sí quedan fuera del alcance convencional (págs. 27
  y 62).
