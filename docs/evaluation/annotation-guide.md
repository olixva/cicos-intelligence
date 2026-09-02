# Guía de anotación del golden set — Allianz RAG

> **Estado:** borrador inicial (2026-09-02). Este documento acompaña al
> cierre integral y se completará a medida que las dobles revisiones se
> cierren. Ningún caso entra al golden congelado sin pasar este flujo.

## 1. Propósito

El golden set es la única referencia que se considera válida para
calibrar y comparar configuraciones de recuperación, generación y
router. No es un dataset de entrenamiento: se usa para medir
recuperación, calidad factual, abstención correcta y errores críticos
sobre casos revisados contra el manual.

## 2. Taxonomía de casos

Cada caso lleva una única `expected_intent` y, según ella, pertenece a
una de estas familias:

| Familia | Intención esperada | Descripción |
| --- | --- | --- |
| `documental-factual` | `question` | Pregunta directa sobre un dato del manual con respuesta cerrada. |
| `documental-conceptual` | `question` | Pregunta sobre criterio o procedimiento descrito en el manual. |
| `documental-cruzada` | `question` | Pregunta que exige referencias cruzadas (más de una página). |
| `siniestro-caso-real` | `claim` | Siniestro de la prueba original (los cinco casos siguen presentes dentro del golden actual como family_ids `accident-0X-…` con sus variantes ES). |
| `siniestro-contraste` | `claim` | Pares de versiones contradictorias para validar atribución. |
| `siniestro-maniobra` | `claim` | Maniobra, cruce, estacionamiento o peatón. |
| `siniestro-excepcion` | `claim` | Caso donde una excepción documentada cambia la decisión. |
| `siniestro-fuera-convenio` | `claim` | Caso fuera de CIDE/ASCIDE/CICOS. |
| `router-ambiguo` | `clarification_required` | Texto cuya intención no puede decidirse de forma segura. |
| `router-clasificacion-asegurada` | `question` o `claim` | Texto que debe ir a un único recorrido. |
| `tabla-imagen` | `question` o `claim` | Caso que requiere la matriz o un fragmento visual. |
| `edge-adversarial` | `question` o `claim` | Caso construido para detectar alucinaciones o invención de reglas. |
| `out-of-scope` | `out_of_scope` | Consulta fuera del alcance del manual. |

Cada familia se asigna **íntegramente** a `development` o `holdout`.
No se permiten paráfrasis, traducciones o variantes cruzando
particiones. La función `check_family_splits` lo verifica en cada
publicación.

## 3. Esquema por caso

Cada caso es un objeto JSON con tres campos nativos de Langfuse
(`input`, `expected_output`, `metadata`) y el esquema versionado
`1.0.0` (ver `docs/evaluation/golden-schema.json`).

### 3.1 `input`

* `text`: literal del enunciado que verá el sistema. Sin corrección de
  estilo, sin resumen y sin reformulación del asistente. Si el usuario
  añade aclaraciones se incluyen en `clarifications`.
* `language`: `es` o `en`.
* `clarifications`: mensajes adicionales del usuario, sin respuesta del
  asistente mezclada.

### 3.2 `expected_output`

* `reference`: respuesta literal esperada. Es la verdad documental; no
  es la única formulación admisible (ver `acceptable_alternatives`).
* `decisions`: triple cerrada de intención y decisiones.
  * `intent`: `question | claim | clarification_required`.
  * `answer_status`: `answered | partial | insufficient_evidence | out_of_scope`
    (obligatorio en `question`, nulo en `claim` y `clarification_required`).
  * `applicability`: `applicable | not_applicable | undetermined`
    (obligatorio en `claim`).
  * `convention`: `CIDE | ASCIDE` (obligatorio en `claim` cuando
    `applicability` es `applicable`).
  * `claim_decision`: `resolved | conditional | undetermined | not_assessed`
    (obligatorio en `claim`).
* `requirements`: lista no vacía de requisitos de respuesta que el
  sistema debe cubrir. Se referencian desde `evidence_requirements` y
  desde `acceptable_alternatives.satisfies`.
* `acceptable_alternatives`: formulaciones alternativas aceptables.
  Cada alternativa declara qué requisitos satisface.
* `forbidden_facts`: hechos que el sistema **no debe** afirmar. Sirven
  para detectar alucinaciones e invenciones de reglas.
* `evidence_requirements`: los identificadores de evidencia (`page:N`
  o `element:...`) que la respuesta debe poder mostrar. Se modelan con
  un requisito externo en AND (`bundle.all_of`) y alternativas en OR
  (`requirement.any_of`).

### 3.3 `metadata`

* `case_id`: identificador único del caso (`c-…`).
* `family_id`: identificador de familia. Todas las variantes de una
  misma familia comparten este campo.
* `partition`: `development` o `holdout`.
* `review_status`: estado de revisión.
  * `candidate`: aún no revisado por segunda persona.
  * `in_review`: en curso.
  * `adjudicated`: revisado por al menos dos personas y resuelto.
  * `quarantined`: descartado o pendiente de re-anotación.
* `provenance.kind`:
  * `interview_example`: los cinco casos originales de la prueba (siguen presentes dentro del golden actual como family_ids `accident-0X-…` con sus variantes ES).
  * `manual_derived`: derivado de una página concreta del manual.
  * `adversarial`: construido para cazar errores.
  * `synthetic`: generado por `TestsetGenerator` y revisado.
  * `technical_fixture`: solo para verificar la maquinaria.
* `language`, `expected_intent`: deben coincidir con los campos
  correspondientes en `input` y `expected_output.decisions.intent`.

### 3.4 `metadata.review`

* `reviewer_ids`: al menos dos identificadores de revisores.
* `independent_resolution_checked`: el revisor **no vio** la etiqueta
  propuesta al emitir su resolución.
* `evidence_checked`: cada identificador de evidencia existe en la
  publicación del parser correspondiente.
* `adversarial_checked`: el caso fue revisado buscando contraejemplos
  documentados en el manual (maniobra no contemplada, excepción
  ignorada, etc.).
* `adjudication_note`: justificación textual de la decisión final.
* `open_discrepancies`: lista vacía para casos `adjudicated`. Cualquier
  discrepancia abierta marca el caso como `quarantined`.

## 4. Flujo de revisión

1. **Generación**: el redactor crea el caso en estado `candidate`. Solo
   `provenance.kind = interview_example` puede saltarse la generación.
2. **Revisión ciega**: un revisor independiente recibe el caso sin la
   etiqueta propuesta y emite su propia resolución. Se compara.
3. **Contraste con PDF**: cada evidencia se abre en el PDF original y
   se confirma la página física y la etiqueta impresa cuando exista.
4. **Adjudicación**: si coinciden, el caso pasa a `adjudicated`. Si no,
   se documenta la discrepancia; o se ajusta el caso, o se mueve a
   `quarantined`. Ningún caso con discrepancias abiertas entra al
   congelado.
5. **Adversarial**: tercer pase que busca errores del propio sistema
   (alucinación de regla, cita inventada, conclusión definitiva con
   datos ausentes).

## 5. Publicación y congelación

* `data/evaluation/golden/development.jsonl` y `holdout.jsonl` son
  los archivos canónicos de desarrollo.
* `allianz golden validate --release RELEASE` valida todos los items
  contra el esquema, verifica la separación de familias, comprueba que
  la evidencia referenciada existe en el parser declarado y exige
  revisión completa.
* `allianz golden freeze --dataset NAME --release ID` solo se ejecuta
  si la validación pasa. Crea `data/evaluation/golden/releases/ID/`
  con `items.jsonl`, `manifest.json` y `schema.json`. La SHA-256 del
  contenido entra en el manifiesto y se vuelve a comprobar antes de
  cualquier evaluación.
* `allianz golden publish --dataset NAME --release ID` empuja la
  release a un dataset Langfuse con `metadata.partition` por item.
* El holdout permanece sellado. Ningún experimento lo usa durante
  selección. Se abre una sola vez tras congelar el código y los
  umbrales.

## 6. Lo que el sistema **no** puede hacer para crear un caso

* No convierte tablas extraídas por Docling en reglas automáticas.
* No usa el mismo motor de reglas que se va a evaluar para anotar la
  etiqueta correcta.
* No recurre a votación entre LLMs como prueba experta; el acuerdo
  entre modelos se anota como revisión automática.
* No aprueba una respuesta cuya evidencia no se haya contrastado con
  el PDF original.
