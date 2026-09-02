# Cierre y entrega final — Allianz CICOS Claims Intelligence

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Apply superpowers:test-driven-development for every behavior change and superpowers:verification-before-completion before each phase gate. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cerrar la prueba técnica de Allianz con los tres entregables que exige el enunciado (presentación, documento de arquitectura y código) y un sistema que resuelva con honestidad los cinco siniestros del enunciado en una demo en vivo de 30-45 min.

**Architecture:** Se mantienen los límites hexagonales actuales. La matriz CIDE y el corpus de reglas pasan de ausentes a artefactos versionados con doble transcripción independiente y attestation firmada. El flujo de siniestros deja de abstenerse por falta de datos y pasa a abstenerse *sólo* cuando el Convenio realmente no aplica, emitiendo `rules_evaluated` reales. Backend sigue siendo la única fuente de verdad de etapas, tiempos y trazas.

**Tech Stack:** Python 3.14, FastAPI, LangGraph, Qdrant, Langfuse, Docling, pypdf, pypdfium2, OpenAI SDK, Ragas, React 19, TypeScript, Vite, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-08-31-allianz-rag-design.md`
**Enunciado original:** `docs/enunciado/GenAI_Interview_Instructions.docx` (se copia en Task 0)
**Plan anterior (vigente, se subsume aquí):** `docs/superpowers/plans/2026-09-02-remediacion-ux-observabilidad.md`
**Auditoría de referencia:** `docs/audit/2026-09-02-auditoria-integral-specs.md`

---

## Contexto medido en el arranque de este plan (2026-09-02)

No repetir esta verificación a ciegas; son cifras ejecutadas, no citadas de handoffs.

| Gate | Estado medido |
|---|---|
| `make test-backend` | 331 passed, 1 skipped, exit 0 |
| `make check-frontend` | lint + typecheck + 51 tests + build, exit 0 |
| `make lint-backend` | **FALLA**: F821 `LangGraphQuestionWorkflow` en `backend/tests/test_question_workflow.py:210` |
| `make check-openapi` | **FALLA**: drift en `components` |
| `origin/main` | `88d93cb` — **10 commits locales sin pushear** |

Trabajo sin commitear (7 ficheros): propagación de `trace_url_factory` desde `bootstrap` hasta el envelope, usando `Langfuse.get_trace_url()` en lugar de concatenar `/trace/{id}`. Es correcto y trae tests; sólo rompe los dos gates de arriba.

Artefactos ausentes verificados: `data/rules/` contiene sólo los dos `*.schema.json`; `data/evaluation/golden/` contiene sólo `releases/` vacío; `data/extractions/` contiene sólo la publicación `pypdf-6.16.2`.

### Correcciones a los handoffs heredados

Los documentos de traspaso (`.slim/deepwork/*`, `docs/handoff-2026-09-01.md`) contienen afirmaciones que **no** se sostienen contra el código actual. Verificado en este arranque:

- **T10 no está "pendiente de re-añadir en backend".** El handoff `.slim` describe un revert de `queries.py`; el commit `73516e1` ya lo cerró y los eventos SSE llevan `event_id` y `timestamp`, con `dispatch` sólo en modo `auto`. Lo que falta de T10 es **el lado frontend**: `frontend/src/lib/thread-state.ts` ignora esos campos, genera sus propios instantes con `Date.now()` (líneas 181 y 186) y **escribe `durationMs: 0` a mano** en las líneas 505 y 516. Las duraciones que ve el usuario siguen siendo fabricadas.
- **`GET /api/v1/demo/cases` no existe.** La spec lo lista en su tabla de capacidades HTTP (sección 8) y ninguna auditoría previa lo señaló. Las otras nueve rutas de la spec sí están registradas y responden.
- **El dimensionado del golden de los handoffs es inferior al de la spec.** La spec (sección 9) fija orientativamente **~70 casos: 50 de desarrollo y 20 de reserva**, con los cinco originales en desarrollo, y advierte de que las 324 celdas de la matriz son un control de extracción independiente, **no** 324 accidentes.
- **La auditoría integral está desactualizada en su recuento de tests** (dice 292 passed y `ruff format` fallando en 25 ficheros). Hoy son 331 passed y `format-check` pasa. Sus dictámenes cualitativos sobre golden, matriz y evaluación **sí** siguen vigentes.
- **Confirmado como correcto:** `backend/src/domain/rules/applicability.py` implementa exactamente la puerta de dos vehículos + colisión directa + tercero identificado + colisión en cadena, con evidencia obligatoria. Es la base sobre la que se apoyan los siniestros 2 y 3 del enunciado.

Identidad de las fuentes verificada por hash en este arranque: el `.docx` entregado por el usuario da `8561213339f76c7bd8a6c56fa0c91323c6d838ae0e9d0f30a12d8e3f775a4957`, que coincide con el registrado en la spec; el PDF da `b9c70c74...54c8344` tanto en `~/Downloads` como en `data/raw/`.

## Lo que realmente pide el enunciado

El enunciado (`GenAI_Interview_Instructions.docx`) exige **tres** entregables, y dos de ellos no existen en el repositorio:

1. **PowerPoint** con plan de implementación, hitos, supuestos, riesgos y racional de las decisiones técnicas. — **AUSENTE**
2. **Documento explicativo** de arquitectura, decisiones técnicas y retos encontrados. — **AUSENTE**
3. **Código fuente** con scripts de carga, preprocesado, generación y evaluación. — Presente y sólido.

Además: exposición en vivo de **30-45 min** respondiendo preguntas de siniestros, y una "**basic** evaluation for the quality of the responses" — el listón de evaluación del enunciado es explícitamente básico, no un programa experimental completo.

### Los cinco siniestros del enunciado y su tratamiento correcto

Este es el guion de la demo. Cuatro de los cinco caen **fuera** del Convenio, y ese es precisamente el punto fuerte del sistema: la arquitectura ya está construida para abstenerse con criterio.

| # | Relato | Tratamiento correcto | Evidencia en el manual |
|---|---|---|---|
| 1 | A parado en semáforo, B le alcanza por detrás; B alega frenada brusca | **CIDE aplica**: dos vehículos, colisión directa. Resolver por tabla de culpabilidad. | pág. 56, pág. 101-102 (tabla) |
| 2 | Colisión múltiple de cinco coches bajo lluvia, con heridos | **No aplica Convenio**: más de dos vehículos y colisión en cadena. | pág. 56-57 |
| 3 | Coche aparcado dañado en parking, autor huido no identificado | **No aplica Convenio**: no hay segundo vehículo identificado ni D.A.A. | pág. 57 |
| 4 | Cambio de carril con roce, versiones contradictorias | **ASCIDE, norma subsidiaria b.10**: culpable el que cambia de carril, con independencia de la ubicación de los daños. | pág. 75 |
| 5 | B colisiona a A bajo influencia del alcohol, heridos graves, detención | Convenio se evalúa por las circunstancias de la colisión; lo penal y los daños personales quedan **fuera del alcance del Convenio**. | pág. 56 + alcance del manual |

## Global Constraints

Copiadas literalmente del cuerpo de decisiones ya establecido. Aplican a **todas** las tareas.

- No inventar métricas, trazas, tiempos, reglas evaluadas ni resultados.
- No usar la matriz para decidir hasta que exista attestation firmada con dos transcripciones independientes.
- No abrir el holdout durante desarrollo o selección.
- El manual es la edición de **noviembre de 2004**; nunca afirmar que es derecho vigente.
- Un relato aportado por el usuario es distinto de la evidencia recuperada del manual. Los hechos conservan `asserted_by` y `source_text` literal; las contradicciones se mantienen explícitas.
- Backend es la única fuente de verdad de etapas, timestamps y duraciones.
- No publicar métricas sin versionar dataset, perfil, prompt, modelos, commit y hashes.
- Nunca leer, imprimir ni commitear `.env`, `ops/local.env`, claves de Langfuse ni la clave de OpenAI.
- Cada tarea empieza con un test rojo o un validador que falle, y termina con evidencia ejecutada.
- `SHA-256` del manual: `b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344`. Cualquier artefacto que lo cite debe usar exactamente este valor.
- Los identificadores de evidencia tienen la forma `sha256:<hash>:page:<n>` donde `<n>` es la **página física del PDF** (1-indexada), no la impresa. La tabla CIDE está en la página física **101** (impresa 102).

## Línea de corte por plazo

El plazo real es de 1-2 días. Las tareas están ordenadas para que cualquier corte deje una entrega coherente.

- **Imprescindible para entregar** (sin esto no hay entrega válida): Tasks 0, 1, 2, 3, 4, 11, 12.
- **Muy alto valor si hay tiempo**: Tasks 5, 6, 8.
- **Deseable**: Tasks 7, 9, 10.
- **Sólo con margen holgado**: Task 13.

Si se agota el tiempo, lo que queda fuera se documenta como limitación explícita en el documento de arquitectura (Task 11). No se maquilla.

---

## Estructura de ficheros

Ficheros nuevos que introduce este plan:

| Fichero | Responsabilidad |
|---|---|
| `docs/enunciado/GenAI_Interview_Instructions.docx` | El enunciado original, versionado con la entrega. |
| `backend/scripts/render_pdf_page.py` | Renderiza una página física del PDF a PNG para transcripción visual. Sin dependencia de Docling. |
| `backend/scripts/transcribe_matrix_textlayer.py` | Transcripción B: deriva la matriz desde la capa de texto de pypdf. Independiente de la lectura visual. |
| `data/rules/transcriptions/matrix-visual-a.json` | Transcripción A (lectura visual del render 300 dpi). Cruda, sin reconciliar. |
| `data/rules/transcriptions/matrix-textlayer-b.json` | Transcripción B (capa de texto). Cruda, sin reconciliar. |
| `data/rules/cide-matrix.v1.json` | Artefacto adjudicado y firmado, conforme a `cide-matrix.schema.json`. |
| `data/rules/ruleset.v1.json` | Reglas de aplicabilidad y normas subsidiarias ASCIDE, conforme a `ruleset.schema.json`. |
| `data/rules/daa-circumstances.v1.json` | Catálogo de las 18 casillas del apartado 12 de la D.A.A. Marcado como **externo al manual**. |
| `backend/src/domain/models/rule_evaluation.py` | `RuleEvaluation`: inputs, resultado y evidencia de cada regla aplicada. |
| `backend/src/domain/rules/ruleset.py` | Evaluador determinista del ruleset cargado. |
| `backend/src/infrastructure/config/rules_artifacts.py` | Carga y valida los artefactos al arranque; falla ruidosamente si no cuadran. |
| `data/evaluation/golden/interview.jsonl` | Los cinco siniestros del enunciado, anotados. |
| `data/evaluation/golden/documental.jsonl` | Preguntas documentales con evidencia identificada. |
| `docs/entrega/arquitectura.md` | Entregable 2 del enunciado. |
| `docs/entrega/presentacion.pptx` | Entregable 1 del enunciado. |
| `docs/entrega/guion-demo.md` | Guion determinista de la demo de 30-45 min. |

---

### Task 0: Sanear el árbol, cerrar gates y publicar

El árbol tiene trabajo valioso sin commitear que rompe dos gates, y 10 commits sin pushear. Nada más puede empezar encima de una base roja.

**Files:**
- Modify: `backend/tests/test_question_workflow.py:205-256`
- Modify: `docs/api/openapi.json`
- Create: `docs/enunciado/GenAI_Interview_Instructions.docx`

**Interfaces:**
- Produces: árbol limpio, `make check-backend` y `make check-openapi` en verde, `origin/main` al día. Todas las tareas siguientes lo asumen.

- [ ] **Step 1: Reproducir el fallo de lint**

```bash
make lint-backend
```

Esperado: `F821 Undefined name 'LangGraphQuestionWorkflow'` en `backend/tests/test_question_workflow.py:210`.

La causa: el tipo se usa en la anotación de retorno a nivel de módulo, pero se importa dentro del cuerpo de la función. En Python 3.14 las anotaciones son perezosas y no se evalúan, por eso los tests pasan; ruff lo detecta igualmente y tiene razón.

- [ ] **Step 2: Subir el import al nivel de módulo**

En `backend/tests/test_question_workflow.py`, borrar el import interno y la construcción indirecta del helper `_stub_workflow_fixtures`, dejándolo así:

```python
def _stub_workflow_fixtures(*, trace_id: str, trace_url: str | None) -> LangGraphQuestionWorkflow:
    """Build the minimum stubs that drive the question workflow to a real answer."""

    page = _page()
    chunk = Chunk(
        chunk_id="chunk-1",
        text="Fragmento.",
        evidence_ids=(page.evidence_id,),
    )
    answer = QuestionAnswer("answered", (AnswerBlock("Respuesta.", (page.evidence_id,)),))
    return LangGraphQuestionWorkflow(
        retriever=FakeRetriever(chunks=(chunk,)),
        evidence_repository=FakeEvidenceRepository(pages=(page,)),
        language_model=FakeLanguageModel(answer=answer),
        trace_id_factory=lambda: trace_id,
        trace_url_factory=(lambda _trace_id: trace_url) if trace_url is not None else None,
    )
```

Comprobar que `LangGraphQuestionWorkflow` ya está importado arriba del fichero; si no lo está, añadirlo al bloque de imports existente.

- [ ] **Step 3: Verificar lint y tests**

```bash
make lint-backend && make format-check && make test-backend
```

Esperado: exit 0 en los tres. El recuento de tests debe seguir siendo 331 passed, 1 skipped.

- [ ] **Step 4: Regenerar el snapshot de OpenAPI**

```bash
uv run --project backend python backend/scripts/export_openapi.py
make check-openapi
```

Esperado: `check-openapi` en verde. Revisar el diff de `docs/api/openapi.json` y confirmar que los únicos cambios son la aparición de `trace_url` en `QuestionResult` y `ClaimResult`. Cualquier otro cambio es una regresión que hay que investigar antes de commitear.

- [ ] **Step 5: Versionar el enunciado**

```bash
mkdir -p docs/enunciado
cp "/Users/aoc/Downloads/GenAI_Interview_Instructions.docx" docs/enunciado/
```

- [ ] **Step 6: Commit y push**

```bash
git add -A
git commit -m "fix(observability): expose canonical Langfuse trace_url end to end

Propagate a trace_url_factory from bootstrap through both LangGraph
workflows into the API envelope so links come from Langfuse
get_trace_url() instead of a hand-built /trace/{id} suffix. Fix the
module-level annotation in the new workflow test and refresh the
OpenAPI snapshot. Version the original interview brief alongside the
delivery."
git push origin HEAD:main
```

- [ ] **Step 7: Confirmar la publicación**

```bash
git log --oneline origin/main -1
```

Esperado: el hash del commit recién creado, no `88d93cb`.

---

### Task 1: Transcribir y adjudicar la matriz CIDE 18×18

Sin este artefacto el flujo de siniestros nunca sale de `undetermined` y el siniestro #1 del enunciado no se puede resolver. El protocolo (`docs/rules/transcription-protocol.md`) exige dos transcripciones independientes y adjudicación humana; se satisface con dos rutas de extracción genuinamente distintas más la firma del usuario.

**Files:**
- Create: `backend/scripts/render_pdf_page.py`
- Create: `backend/scripts/transcribe_matrix_textlayer.py`
- Create: `data/rules/transcriptions/matrix-visual-a.json`
- Create: `data/rules/transcriptions/matrix-textlayer-b.json`
- Create: `data/rules/cide-matrix.v1.json`
- Test: `backend/tests/test_matrix_transcription.py`

**Interfaces:**
- Consumes: `validate_cide_matrix(artifact_path, *, expected_document_hash, evidence_pool) -> RulesValidationReport` y `compare_transcriptions(left, right) -> dict[str, object]` de `domain.rules.artifact_validation`; `transcription_sha256(path) -> str` del mismo módulo.
- Produces: `data/rules/cide-matrix.v1.json` válido (324 celdas, attestation completa), consumible por `load_matrix_cells(path) -> dict[tuple[int, int], dict[str, Any]]`.

**Contexto que el implementador necesita:** la tabla está en la página **física 101** del PDF (impresa "102"), titulada "56. Tabla de Culpabilidad Convenio CIDE (continuación)". Filas `A0`–`A17`, columnas `B0`–`B17`. Los valores impresos son exactamente `A`, `B`, `-`, `A*` y `B*`. La diagonal es siempre `-`. Bajo la tabla hay cuatro observaciones que gobiernan las celdas marcadas con asterisco:

```
A2 + B4  = Culpable B, salvo que el A abra la puerta.
B2 + A4  = Culpable A, salvo que el B abra la puerta.
A16 + B0 = Culpable B, salvo que el A circule por vía sin pavimentar.
B16 + A0 = Culpable A, salvo que el B circule por vía sin pavimentar.
```

- [ ] **Step 1: Escribir el script de render**

Crear `backend/scripts/render_pdf_page.py`:

```python
"""Render one physical PDF page to PNG for human/visual transcription.

Deliberately independent from the Docling pipeline: transcription B must
not share an extraction path with transcription A.
"""

import argparse
from pathlib import Path

import pypdfium2 as pdfium


def render(source: Path, page: int, output: Path, dpi: int) -> Path:
    """Render the 1-indexed physical page and return the written path."""
    if page < 1:
        raise ValueError("page must be a positive 1-indexed physical page number")
    document = pdfium.PdfDocument(source)
    if page > len(document):
        raise ValueError(f"page {page} is beyond the {len(document)}-page document")
    image = document[page - 1].render(scale=dpi / 72).to_pil()
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--page", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dpi", type=int, default=300)
    args = parser.parse_args()
    written = render(args.source, args.page, args.output, args.dpi)
    print(written)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Renderizar la página de la tabla**

```bash
uv run --project backend --group ingestion python backend/scripts/render_pdf_page.py \
  data/raw/Manual-cide-ascide-y-cicos.pdf \
  --page 101 --dpi 300 \
  --output /tmp/allianz-matrix/page-101.png
```

Esperado: imprime la ruta; el PNG mide 2480×3509.

- [ ] **Step 3: Producir la transcripción A (visual)**

Leer el PNG y transcribir las 324 celdas **sin consultar la capa de texto ni el script del Step 5**. Escribir `data/rules/transcriptions/matrix-visual-a.json` con esta forma exacta (fragmento ilustrativo; hay que completar las 324 entradas):

```json
{
  "transcription_id": "matrix-visual-a",
  "method": "visual-render-300dpi",
  "reviewer_id": "claude-visual-a",
  "pdf_page": 101,
  "document_hash": "b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344",
  "row_labels": ["A0", "A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9", "A10", "A11", "A12", "A13", "A14", "A15", "A16", "A17"],
  "column_labels": ["B0", "B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B9", "B10", "B11", "B12", "B13", "B14", "B15", "B16", "B17"],
  "cells": {
    "0,0": { "a": 0, "b": 0, "outcome": "-" },
    "0,1": { "a": 0, "b": 1, "outcome": "A" },
    "0,16": { "a": 0, "b": 16, "outcome": "A*" }
  }
}
```

Regla de indexación: la clave es `"<a>,<b>"` con `a` = índice de fila `A<a>` y `b` = índice de columna `B<b>`, ambos de 0 a 17. El schema exige `a` y `b` entre 1 y 18, así que la conversión a base-1 se hace en el Step 7, no aquí.

- [ ] **Step 4: Escribir el test rojo del script de capa de texto**

Crear `backend/tests/test_matrix_transcription.py`:

```python
"""The text-layer transcription must reproduce the printed grid exactly."""

from pathlib import Path

from scripts.transcribe_matrix_textlayer import parse_matrix_text

_PAGE_101_EXCERPT = (
    " 102 56. Tabla de Culpabilidad Convenio CIDE (continuación) "
    "B0 B1 B2 B3 B4 B5 B6 B7 B8 B9 B10 B11 B12 B13 B14 B15 B16 B17 "
    "A0 - A B B B B B A B - B B B B B B A* B "
)


def test_parse_matrix_text_reads_the_header_row() -> None:
    parsed = parse_matrix_text(_PAGE_101_EXCERPT)
    assert parsed["column_labels"][:3] == ["B0", "B1", "B2"]
    assert len(parsed["column_labels"]) == 18


def test_parse_matrix_text_preserves_asterisked_outcomes() -> None:
    parsed = parse_matrix_text(_PAGE_101_EXCERPT)
    assert parsed["cells"]["0,16"]["outcome"] == "A*"
    assert parsed["cells"]["0,0"]["outcome"] == "-"


def test_parse_matrix_text_rejects_a_short_row() -> None:
    truncated = _PAGE_101_EXCERPT.replace("A* B ", "")
    try:
        parse_matrix_text(truncated)
    except ValueError as error:
        assert "18" in str(error)
    else:
        raise AssertionError("a row with fewer than 18 outcomes must be rejected")
```

- [ ] **Step 5: Verificar que el test falla**

```bash
uv run --project backend pytest backend/tests/test_matrix_transcription.py -v
```

Esperado: FAIL con `ModuleNotFoundError: No module named 'scripts.transcribe_matrix_textlayer'`.

- [ ] **Step 6: Implementar la transcripción B**

Crear `backend/scripts/transcribe_matrix_textlayer.py`. El parser debe: localizar la fila de cabecera `B0 … B17`, luego consumir 18 filas que empiecen por `A0`…`A17`, y exigir exactamente 18 valores por fila del conjunto `{A, B, -, A*, B*}`. Rechazar con `ValueError` cualquier fila que no traiga 18 valores — un parser silenciosamente permisivo destruiría el valor de tener dos transcripciones. Debe exponer:

```python
def parse_matrix_text(text: str) -> dict[str, object]:
    """Parse the printed CIDE grid out of the pypdf text layer."""
```

y un `main()` que lea `pages.jsonl` de la publicación pypdf, tome el registro con `pdf_page == 101`, y escriba `data/rules/transcriptions/matrix-textlayer-b.json` con el mismo esquema del Step 3 pero `"transcription_id": "matrix-textlayer-b"`, `"method": "pypdf-text-layer"`, `"reviewer_id": "claude-textlayer-b"`.

- [ ] **Step 7: Verificar que los tests pasan y generar la transcripción B**

```bash
uv run --project backend pytest backend/tests/test_matrix_transcription.py -v
uv run --project backend python backend/scripts/transcribe_matrix_textlayer.py
```

Esperado: 3 passed; se escribe `data/rules/transcriptions/matrix-textlayer-b.json` con 324 celdas.

- [ ] **Step 8: Comparar las dos transcripciones**

```bash
uv run --project backend allianz rules compare-transcriptions \
  data/rules/transcriptions/matrix-visual-a.json \
  data/rules/transcriptions/matrix-textlayer-b.json
```

Esperado: JSON con `compared_cells: 324`. Registrar `matching_cells` y la lista de `differences`.

- [ ] **Step 9: PARADA — adjudicación humana**

Presentar al usuario **únicamente**: (a) el número de celdas coincidentes sobre 324, (b) la lista completa de divergencias con el recorte visual de cada celda en disputa, (c) las cuatro observaciones al pie transcritas. No continuar sin su resolución explícita de cada divergencia y sin su identificador para `signed_by`.

Si el número de coincidencias es 324/324, decírselo tal cual y pedir igualmente la firma: la ausencia de divergencias no sustituye a la adjudicación.

- [ ] **Step 10: Construir el artefacto adjudicado**

Escribir `data/rules/cide-matrix.v1.json` conforme a `data/rules/cide-matrix.schema.json`. Puntos que el schema exige y son fáciles de fallar:

- `a` y `b` en cada celda van de **1 a 18** (base-1), mientras que las etiquetas impresas son `A0`–`A17`. La celda `A0/B0` es `{"a": 1, "b": 1}` y su clave de `cells` sigue siendo la que usa `load_matrix_cells`, que hace `key.split(",")` — usar claves `"1,1"` … `"18,18"`.
- `orientation` debe ser `"A-row-B-column"`, que es lo impreso.
- `evidence_ids` de cada celda: `["sha256:b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344:page:101"]`.
- `normalized_outcome`: `A` → `"A_full"`, `B` → `"B_full"`, `-` → `"no_convention"`, `A*` y `B*` → `"exception"`. El campo `outcome` conserva el literal impreso.
- `notes`: las cuatro observaciones, con `note_id` `obs-a2-b4`, `obs-b2-a4`, `obs-a16-b0`, `obs-b16-a0`, cada una con el mismo `evidence_ids` de la página 101.
- `reviewer_ids`: `["claude-visual-a", "claude-textlayer-b", "<id del usuario>"]`.
- `attestation.transcriptions`: dos entradas, con `independent: true`, `pdf_page_checked: true` y `transcription_sha256` calculado con:

```bash
uv run --project backend python -c "
from pathlib import Path
from domain.rules.artifact_validation import transcription_sha256
for name in ('matrix-visual-a', 'matrix-textlayer-b'):
    p = Path(f'data/rules/transcriptions/{name}.json')
    print(name, transcription_sha256(p))
"
```

- `attestation.divergence_resolution`: texto real de cómo se resolvió cada divergencia contra el PDF, no una fórmula genérica.
- `attestation.signed_by`: el identificador que dé el usuario en el Step 9.

- [ ] **Step 11: Validar el artefacto**

```bash
uv run --project backend allianz rules validate \
  --matrix data/rules/cide-matrix.v1.json \
  --expected-document-hash b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344 \
  --evidence-roots data/extractions
```

Esperado: `ok: true`, `cell_count: 324`, `unknown_evidence: []`, `attestation_complete: true`. Si sale `unknown_evidence`, el `evidence_id` de la página 101 no coincide con el publicado: comprobarlo con
`grep -m1 'page:101' data/extractions/*/pypdf-6.16.2/pages.jsonl`.

- [ ] **Step 12: Commit**

```bash
git add backend/scripts/render_pdf_page.py backend/scripts/transcribe_matrix_textlayer.py \
        backend/tests/test_matrix_transcription.py data/rules/
git commit -m "feat(rules): transcribe and attest the CIDE 18x18 responsibility matrix

Two independent extraction paths — a 300 dpi visual read and a pypdf
text-layer parser — produce separate raw transcriptions. Divergences
were adjudicated against the source page and signed off. The matrix
now validates with a complete attestation, so the claim workflow may
begin resolving cells."
git push origin HEAD:main
```

---

### Task 2: Construir el ruleset v1 y el catálogo de circunstancias

La matriz sola no basta: hace falta el corpus de reglas de aplicabilidad y las normas subsidiarias ASCIDE (que resuelven el siniestro #4 del enunciado), y el catálogo de las 18 casillas del apartado 12 sin el cual no se puede mapear un relato a una celda.

**Files:**
- Create: `data/rules/ruleset.v1.json`
- Create: `data/rules/daa-circumstances.v1.json`
- Create: `backend/src/domain/models/rule_evaluation.py`
- Create: `backend/src/domain/rules/ruleset.py`
- Test: `backend/tests/test_ruleset_evaluation.py`

**Interfaces:**
- Consumes: `validate_ruleset(artifact_path, *, expected_document_hash, evidence_pool) -> RulesValidationReport`.
- Produces:
  - `RuleEvaluation(rule_id: str, inputs: tuple[tuple[str, str], ...], result: Literal["matched", "not_matched", "insufficient_data"], evidence_ids: tuple[str, ...], rationale: str)` — frozen dataclass con slots.
  - `evaluate_ruleset(rules: tuple[LoadedRule, ...], facts: Mapping[str, str]) -> tuple[RuleEvaluation, ...]`.

**Contexto crítico — limitación que hay que declarar, no ocultar:** el manual **no define** qué maniobra representa cada casilla `A0`…`A17`. Son las casillas del apartado 12 del parte amistoso europeo (D.A.A.), un formulario externo al manual. `data/rules/daa-circumstances.v1.json` es por tanto un artefacto de **procedencia externa**, y debe llevar `"provenance": "external-daa-form"` y `"in_manual_scope": false` en su cabecera. El sistema nunca debe citar el manual como fuente de estas etiquetas, y el documento de arquitectura (Task 11) debe recoger esta limitación explícitamente.

- [ ] **Step 1: Escribir el test rojo del modelo de evaluación**

Crear `backend/tests/test_ruleset_evaluation.py`:

```python
"""A rule evaluation must carry its own inputs, result and evidence."""

import pytest

from domain.models.rule_evaluation import RuleEvaluation


def test_rule_evaluation_keeps_inputs_and_evidence() -> None:
    evaluation = RuleEvaluation(
        rule_id="cide-two-vehicles",
        inputs=(("vehicle_count", "2"), ("direct_collision", "true")),
        result="matched",
        evidence_ids=("sha256:" + "0" * 64 + ":page:56",),
        rationale="Dos vehículos con colisión directa.",
    )
    assert evaluation.inputs == (("vehicle_count", "2"), ("direct_collision", "true"))
    assert evaluation.result == "matched"


def test_rule_evaluation_rejects_a_matched_result_without_evidence() -> None:
    with pytest.raises(ValueError, match="evidence"):
        RuleEvaluation(
            rule_id="cide-two-vehicles",
            inputs=(("vehicle_count", "2"),),
            result="matched",
            evidence_ids=(),
            rationale="Sin evidencia.",
        )


def test_rule_evaluation_rejects_an_empty_rationale() -> None:
    with pytest.raises(ValueError, match="rationale"):
        RuleEvaluation(
            rule_id="cide-two-vehicles",
            inputs=(),
            result="insufficient_data",
            evidence_ids=(),
            rationale="   ",
        )
```

- [ ] **Step 2: Verificar que falla**

```bash
uv run --project backend pytest backend/tests/test_ruleset_evaluation.py -v
```

Esperado: FAIL con `ModuleNotFoundError: No module named 'domain.models.rule_evaluation'`.

- [ ] **Step 3: Implementar el modelo**

Crear `backend/src/domain/models/rule_evaluation.py`:

```python
"""One deterministic rule application, with the inputs and evidence that justify it."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class RuleEvaluation:
    """A rule that actually ran, never a placeholder for one that did not."""

    rule_id: str
    inputs: tuple[tuple[str, str], ...]
    result: Literal["matched", "not_matched", "insufficient_data"]
    evidence_ids: tuple[str, ...]
    rationale: str

    def __post_init__(self) -> None:
        if not self.rule_id.strip():
            raise ValueError("rule_id must be nonempty")
        if not self.rationale.strip():
            raise ValueError("rationale must be nonempty")
        if self.result == "matched" and not self.evidence_ids:
            raise ValueError("a matched rule must cite the evidence that supports it")
```

- [ ] **Step 4: Verificar que pasan**

```bash
uv run --project backend pytest backend/tests/test_ruleset_evaluation.py -v
```

Esperado: 3 passed.

- [ ] **Step 5: Escribir el ruleset**

Crear `data/rules/ruleset.v1.json` conforme a `data/rules/ruleset.schema.json` (leerlo primero para las claves exactas). Las reglas mínimas, todas con `evidence_ids` reales:

| `rule_id` | Condición | Consecuencia | Evidencia |
|---|---|---|---|
| `cide-requires-two-vehicles` | `vehicle_count != 2` | Convenio no aplicable | página 56 |
| `cide-requires-direct-collision` | `direct_collision == false` | Convenio no aplicable | página 56 |
| `chain-collision-excludes-convention` | `chain_collision == true` | Convenio no aplicable | página 57 |
| `third-vehicle-identified-excludes-cide` | `third_vehicle_identified == true` | CIDE no aplicable; ASCIDE sólo si nadie identifica al tercero | páginas 56-57 |
| `ascide-b10-lane-change` | Ambos reconocen cambio de carril y discrepan en responsabilidad | Culpable quien cambia de carril, con independencia de la ubicación de los daños | página 75 |
| `ascide-b9-reverse-rear-impact` | Versiones opuestas entre alcance trasero y marcha atrás | Responsable quien presenta daños en la parte delantera | página 75 |
| `cide-door-opening` | Tema de puertas sin especificar si se ejercía la acción de abrir | Deudora la aseguradora del vehículo que pudiera estar abriendo | página 91 |

Confirmar cada número de página física releyendo el `text` correspondiente de `pages.jsonl` antes de escribir el `evidence_id`. **No escribir una regla cuya página no se haya releído.**

- [ ] **Step 6: Escribir el catálogo de circunstancias**

Crear `data/rules/daa-circumstances.v1.json` con las 18 casillas del apartado 12 de la D.A.A., cabecera incluida:

```json
{
  "schema_version": "1.0.0",
  "provenance": "external-daa-form",
  "in_manual_scope": false,
  "note": "El manual CIDE/ASCIDE/CICOS no define estas etiquetas. Proceden del apartado 12 del parte amistoso europeo de accidentes. No citar el manual como fuente.",
  "circumstances": [
    { "index": 0, "label": "estacionado / detenido" }
  ]
}
```

- [ ] **Step 7: PARADA — validación humana del catálogo**

Presentar al usuario las 18 etiquetas propuestas y pedirle confirmación. Son la bisagra entre el relato y la celda de la matriz: una etiqueta mal asignada produce decisiones incorrectas con apariencia de rigor. No continuar sin su visto bueno.

- [ ] **Step 8: Implementar el evaluador**

Crear `backend/src/domain/rules/ruleset.py` con `evaluate_ruleset(rules, facts)`. Contrato: devuelve un `RuleEvaluation` **por cada regla del ruleset**, nunca sólo por las que casan. Un hecho ausente produce `result="insufficient_data"`, jamás una suposición.

- [ ] **Step 9: Escribir los tests del evaluador**

Añadir a `backend/tests/test_ruleset_evaluation.py` tests que cubran: regla que casa con todos los hechos; regla con un hecho ausente devuelve `insufficient_data`; el evaluador emite una entrada por regla aunque ninguna case; una regla nunca se marca `matched` sin los `evidence_ids` del artefacto.

- [ ] **Step 10: Validar el artefacto y commitear**

```bash
uv run --project backend allianz rules validate \
  --matrix data/rules/cide-matrix.v1.json \
  --ruleset data/rules/ruleset.v1.json \
  --expected-document-hash b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344 \
  --evidence-roots data/extractions
uv run --project backend pytest backend/tests/test_ruleset_evaluation.py -v
make check-backend
git add data/rules backend/src/domain backend/tests/test_ruleset_evaluation.py
git commit -m "feat(rules): add attested ruleset v1 and the D.A.A. circumstance catalogue

The ruleset encodes convention applicability plus the ASCIDE
subsidiary norms that resolve contradictory lane-change and reversing
versions, each bound to the manual page that states it. The
circumstance catalogue is explicitly marked as external to the manual,
since the source never defines what boxes A0-A17 mean."
git push origin HEAD:main
```

---

### Task 3: Conectar matriz y reglas al flujo de siniestros

Los artefactos existen pero nadie los carga. Esta tarea es la que convierte `undetermined` en una decisión real y hace que `rules_evaluated` deje de ser una promesa.

**Files:**
- Create: `backend/src/infrastructure/config/rules_artifacts.py`
- Modify: `backend/src/domain/models/decision.py` (añadir `rules_evaluated` a `ClaimAnalysis`)
- Modify: `backend/src/infrastructure/adapters/outbound/claim_workflow/langgraph_workflow.py:161-198` (`_apply_rules`)
- Modify: `backend/src/bootstrap.py:190-235` (`build_analyze_claim`)
- Modify: `backend/src/infrastructure/adapters/inbound/api/schemas/envelope.py` (exponer `rules_evaluated`)
- Test: `backend/tests/test_claim_scenarios.py`

**Interfaces:**
- Consumes: `RuleEvaluation`, `evaluate_ruleset`, `load_matrix_cells`, `lookup_matrix(cells, *, a, b, prerequisites_confirmed) -> MatrixLookup`.
- Produces: `ClaimAnalysis` con un campo nuevo `rules_evaluated: tuple[RuleEvaluation, ...] = ()`.

**Invariante que no se puede romper:** `ClaimAnalysis.__post_init__` ya rechaza que una aplicabilidad `not_applicable` produzca decisión `resolved`. Añadir un invariante nuevo: una decisión `resolved` exige al menos un `RuleEvaluation` con `result == "matched"`. Es la barrera que impide que el LLM cuele una conclusión sin regla detrás.

- [ ] **Step 1: Escribir los tests rojos de los cinco siniestros**

Añadir a `backend/tests/test_claim_scenarios.py` un test por cada siniestro del enunciado. Los cinco tests, con la expectativa correcta según la tabla de la cabecera de este plan:

```python
def test_rear_end_at_red_light_resolves_through_the_matrix() -> None:
    """Siniestro 1: dos vehículos, colisión directa. El Convenio aplica y la
    tabla debe resolver; la alegación de frenada brusca no lo impide."""


def test_five_car_pileup_is_outside_the_convention() -> None:
    """Siniestro 2: más de dos vehículos y colisión en cadena. Aplicabilidad
    not_applicable, decisión distinta de resolved, y la regla
    chain-collision-excludes-convention debe aparecer en rules_evaluated."""


def test_hit_and_run_on_a_parked_car_is_outside_the_convention() -> None:
    """Siniestro 3: no hay segundo vehículo identificado ni D.A.A. El sistema
    no puede imputar responsabilidad y debe decirlo."""


def test_lane_change_sideswipe_applies_the_ascide_subsidiary_norm() -> None:
    """Siniestro 4: versiones contradictorias sobre un cambio de carril.
    La norma b.10 imputa al que cambia de carril, citando la página 75."""


def test_drunk_driver_collision_separates_convention_from_criminal_scope() -> None:
    """Siniestro 5: el Convenio se evalúa por las circunstancias de la
    colisión. Lo penal y los daños personales quedan fuera de alcance y
    deben aparecer como limitación explícita, no como silencio."""
```

Cada test debe afirmar sobre `rules_evaluated`: qué reglas corrieron, con qué inputs y con qué evidencia. Un test que sólo compruebe `decision` no protege nada.

- [ ] **Step 2: Verificar que fallan**

```bash
uv run --project backend pytest backend/tests/test_claim_scenarios.py -v
```

Esperado: los cinco nuevos fallan; los 5 tests de honestidad que ya existían siguen pasando. **Si alguno de los antiguos se rompe, parar**: significa que se está degradando una garantía de seguridad ya conquistada.

- [ ] **Step 3: Extender `ClaimAnalysis`**

En `backend/src/domain/models/decision.py`, añadir el campo al final del dataclass (con default, para no romper las construcciones existentes) y el invariante nuevo:

```python
    rules_evaluated: tuple[RuleEvaluation, ...] = ()
```

y dentro de `__post_init__`:

```python
        if self.decision == "resolved" and not any(
            evaluation.result == "matched" for evaluation in self.rules_evaluated
        ):
            raise InvalidDecisionError("a resolved decision must cite at least one matched rule")
```

- [ ] **Step 4: Implementar la carga de artefactos**

Crear `backend/src/infrastructure/config/rules_artifacts.py`. Debe validar en el arranque (reutilizando `validate_cide_matrix` y `validate_ruleset`) y **fallar ruidosamente** si la attestation no está completa. Un arranque que degrada en silencio a "sin matriz" es exactamente el fallo que este proyecto lleva evitando desde el principio.

- [ ] **Step 5: Reescribir `_apply_rules`**

En `langgraph_workflow.py`, tras `assess_applicability`: ejecutar `evaluate_ruleset` sobre los hechos extraídos, y sólo si la aplicabilidad resulta `applicable` y hay posiciones `a`/`b` derivadas del catálogo de circunstancias, llamar a `lookup_matrix` con `prerequisites_confirmed=True`. Mantener intacta la regla ya vigente: la extracción del LLM no puede sobrescribir el resultado determinista.

- [ ] **Step 6: Verificar y commitear**

```bash
uv run --project backend pytest backend/tests/test_claim_scenarios.py -v
make check-backend && make check-openapi
git add -A && git commit -m "feat(claim): resolve claims through the attested matrix and ruleset

The claim workflow now loads the signed artifacts, emits a real
RuleEvaluation per rule with its inputs and evidence, and may resolve a
cell only when applicability holds. A resolved decision without a
matched rule is now a domain error. Covers the five accidents in the
interview brief."
git push origin HEAD:main
```

---

### Task 4: Los cinco siniestros como golden anotado

**Files:**
- Create: `data/evaluation/golden/interview.jsonl`
- Modify: `backend/src/application/models/query.py` (soporte de idioma en el prompt, si falta)
- Test: `backend/tests/test_golden_interview_cases.py`

**Interfaces:**
- Consumes: el esquema golden `1.0.0` ya implementado en `golden_schema.py`; el CLI `allianz golden validate|freeze|publish`.
- Produces: `data/evaluation/golden/interview.jsonl` con cinco casos, partición `dev`.

**Nota sobre idioma:** los cinco relatos del enunciado están **en inglés** y el manual está en español. Hay que verificar que el sistema responde correctamente a un relato en inglés citando evidencia en español. Si no lo hace, es un fallo de demo, no un detalle.

- [ ] **Step 1: Comprobar el comportamiento actual con un relato en inglés**

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/query \
  -H 'content-type: application/json' \
  -d '{"mode":"claim","text":"Vehicle A is stopped at a red light when Vehicle B fails to stop in time and rear-ends Vehicle A. Both drivers claim they were paying attention, but Vehicle B'"'"'s driver insists that Vehicle A stopped suddenly.","language":"en"}' | head -c 2000
```

Registrar la respuesta literal. Si la extracción de hechos falla o la recuperación no trae la página 56, es un defecto a corregir en este mismo task.

- [ ] **Step 2: Anotar los cinco casos**

Escribir `data/evaluation/golden/interview.jsonl`, un caso por línea, siguiendo `docs/evaluation/annotation-guide.md`. Cada caso lleva: `case_id`, `family` (`claim`), `partition` (`dev`), `input.text` (el relato literal del enunciado, en inglés), `expected_output` con la aplicabilidad y decisión esperadas, `expected_evidence_ids` con las páginas de la tabla de la cabecera de este plan, `provenance: "interview_example"` y `review_status`.

- [ ] **Step 3: PARADA — revisión humana**

Presentar los cinco casos anotados al usuario para adjudicación antes de marcarlos `adjudicated`. La guía de anotación prohíbe que el sistema genere su propia referencia.

- [ ] **Step 4: Validar y congelar**

```bash
uv run --project backend allianz golden validate --golden-root data/evaluation/golden
uv run --project backend allianz golden freeze --dataset interview --release v1-interview
```

- [ ] **Step 5: Test de integración contra el golden**

Crear `backend/tests/test_golden_interview_cases.py`: para cada caso del JSONL, ejecutar el workflow con dobles y afirmar que la aplicabilidad y la decisión coinciden con `expected_output`. Marcar con `@pytest.mark.integration` lo que requiera servicios reales.

- [ ] **Step 6: Commit**

```bash
make check-backend
git add data/evaluation backend/tests/test_golden_interview_cases.py
git commit -m "test(golden): annotate and freeze the five interview accidents

Each accident from the brief is annotated with its expected
applicability, decision and manual evidence, reviewed and frozen as
release v1-interview. Four of the five fall outside the convention;
the golden records that abstention is the correct answer, not a gap."
git push origin HEAD:main
```

---

### Task 5: Golden documental y evaluación básica

El enunciado pide "a **basic** evaluation for the quality of the responses". Esto es lo que satisface ese criterio; no hace falta un programa experimental completo.

**Files:**
- Create: `data/evaluation/golden/documental.jsonl`
- Create: `docs/evaluation/resultados-dev.md`

**Dimensionado según la spec, no según los handoffs:** la sección 9 de la spec fija orientativamente **~70 casos, 50 de desarrollo y 20 de reserva**, con los cinco del enunciado en desarrollo y sin que paráfrasis, traducciones o variantes de una familia crucen particiones. Con el plazo real de 1-2 días esa cifra probablemente no se alcance: **reducir el número, nunca la calidad de la revisión**, y declarar el denominador real en `resultados-dev.md`. La spec avisa de que con 20 casos de reserva un solo caso vale cinco puntos porcentuales.

- [ ] **Step 1: Generar candidatos desde evidencia identificada**

Seleccionar preguntas documentales cuya respuesta esté en una página concreta del manual, apuntando al reparto 50/20 de la spec y bajando desde ahí si el tiempo obliga. Generarlas **desde** la evidencia, nunca desde el conocimiento del modelo. Familias a cubrir: aplicabilidad del Convenio, normas subsidiarias ASCIDE, tabla de culpabilidad, D.A.A., y al menos 3 casos fuera de alcance donde la respuesta correcta es abstenerse.

- [ ] **Step 2: PARADA — revisión humana por lotes**

- [ ] **Step 3: Ejecutar el experimento y registrar resultados**

```bash
uv run --project backend allianz golden freeze --dataset documental --release v1-documental
uv run --project backend allianz golden publish --release v1-documental
```

Escribir `docs/evaluation/resultados-dev.md` con: cobertura de evidencia, precisión/recall de citas, tasa de abstención correcta, coste por consulta, y **commit, hashes, perfil, prompts y modelos** de la ejecución. Cifras reales o ninguna.

- [ ] **Step 4: Commit y push**

---

### Task 6: Comparativa de recuperación acotada

Reducida deliberadamente frente al plan anterior: con 1-2 días, la rejilla completa (parser × chunker × modo) no cabe. Se compara lo que la app realmente puede conmutar hoy.

- [ ] **Step 1: Ejecutar dense, BM25 e híbrido sobre `documental.jsonl`** con el mismo perfil, prompt y modelo, variando sólo `retrieval_mode`.
- [ ] **Step 2: Registrar** context recall, context precision, latencia p50/p95 y coste por configuración.
- [ ] **Step 3: Documentar el ganador y los descartes** en `docs/evaluation/resultados-dev.md`, con los criterios declarados **antes** de mirar los resultados.
- [ ] **Step 4: Si el híbrido no gana, cambiar el perfil por defecto.** Mantener `hybrid` hardcodeado porque sí, tras haber medido lo contrario, sería peor que no medir.

---

### Task 7: Router automático medido

- [ ] **Step 1: Reproducir el defecto conocido** de la auditoría: un relato de accidente clasificado como `question`. Los cinco relatos del enunciado son el conjunto de prueba natural.
- [ ] **Step 2: Construir un conjunto balanceado** question/claim/clarification con lenguaje realista y ambiguo, en español **y** en inglés.
- [ ] **Step 3: Medir** matriz de confusión y macro-F1; corregir el prompt del clasificador.
- [ ] **Step 4: Verificar que los modos explícitos no clasifican** — ni en backend ni en frontend. El commit `73516e1` ya lo garantiza en SSE; comprobar que sigue siendo cierto.

---

### Task 8: Langfuse auditable de extremo a extremo

`trace_url` ya está resuelto en Task 0. Falta lo demás.

- [ ] **Step 1:** Propagar un `session_id` estable por conversación desde el frontend hasta la traza. Hoy **no existe ninguna ocurrencia de `session_id` en `backend/src`**.
- [ ] **Step 2:** Una única root trace por request con spans hijos coherentes.
- [ ] **Step 3:** Registrar profile, release, prompts, modelos, latencias, costes, input/output saneados y errores.
- [ ] **Step 4:** Publicar los scores de los evaluadores y verificar Sessions/Experiments/Scores en la UI real.
- [ ] **Gate:** desde un chat se abre su traza, y desde Langfuse se reconstruye la conversación.

---

### Task 9: Historial de conversaciones real

`frontend/src/components/sidebar/thread-sidebar.tsx:18` documenta hoy "Lista de hilos mock (5 hardcoded)". En una demo en vivo, una barra lateral con hilos falsos es un riesgo innecesario.

- [ ] **Step 1:** Sustituir los fixtures por threads reales con `id`, título, timestamps, `mode` y `session_id`, persistidos con `frontend/src/lib/storage.ts`.
- [ ] **Step 2:** Persistir, listar, seleccionar, recargar y eliminar.
- [ ] **Step 3:** Tests de hilo vacío, streaming activo, error, dos pestañas y storage corrupto.
- [ ] **Alternativa aceptable si aprieta el tiempo:** ocultar la barra lateral por completo. Ausencia honesta antes que presencia falsa.

---

### Task 10: Visor de evidencia y pulido de UX

- [ ] **Step 1:** Un único control de cierre, con foco, Escape y retorno de foco.
- [ ] **Step 2:** Materializar la publicación Docling (`allianz ingest --parser docling`) para tener bounding boxes, y propagarlas hasta la API. **Hoy `data/extractions/` sólo contiene `pypdf-6.16.2`**, por eso el visor no puede resaltar región.
- [ ] **Step 3:** Sin región verificada, mostrar fallback explícito a página. Nunca resaltar una región inventada.
- [ ] **Step 4:** Sustituir el BorderBeam azul por feedback sobrio compatible con `prefers-reduced-motion`.
- [ ] **Step 5: Dejar de fabricar duraciones — el resto real de T10.** El backend ya emite `event_id` y `timestamp` por evento desde `73516e1`; el frontend los ignora. Sustituir el `Date.now()` local de `frontend/src/lib/thread-state.ts:181` y los `durationMs: 0` codificados a mano en las líneas 505 y 516 por la diferencia entre los `timestamp` de los eventos SSE recibidos. Añadir un test unitario que falle si un `durationMs` no procede de dos timestamps del backend.
- [ ] **Step 6:** No presentar `undetermined` como éxito — es central, porque cuatro de los cinco siniestros de la demo terminan sin resolución del Convenio y la interfaz tiene que comunicarlo como respuesta correcta y razonada.

---

### Task 11: Documento de arquitectura (entregable 2 del enunciado)

**Files:** Create `docs/entrega/arquitectura.md`

Entregable exigido. Ausente hoy. Debe cubrir:

- [ ] **Step 1: Arquitectura** — hexagonal, dominio/aplicación/infraestructura, por qué FastAPI es infraestructura, por qué dos grafos LangGraph separados y no uno.
- [ ] **Step 2: Ingestión y preprocesado** — pypdf vs Docling, publicaciones inmutables por hash, conservación de páginas en blanco, la limitación OCR de la página 32.
- [ ] **Step 3: Recuperación** — embeddings densos, BM25 en español, RRF nativo de Qdrant, firmas de índice que impiden reutilizar un índice incompatible.
- [ ] **Step 4: Decisiones técnicas y su racional** — por qué la matriz se transcribe con doble vía y attestation en lugar de convertir tablas de Docling automáticamente; por qué el guard determinista prevalece sobre el LLM.
- [ ] **Step 5: Retos encontrados** — la tabla de la página 101 y su extracción; que el manual **no define** las etiquetas `A0`–`A17`; la fragmentación de trazas; la ausencia de ground truth al inicio.
- [ ] **Step 6: Evaluación** — qué se midió, con qué dataset y qué salió.
- [ ] **Step 7: Limitaciones, honestas y enumeradas** — manual de 2004 y no derecho vigente; alcance del Convenio frente a responsabilidad civil general; el catálogo de circunstancias como artefacto externo; todo lo que la línea de corte haya dejado fuera.

---

### Task 12: Presentación (entregable 1 del enunciado)

**Files:** Create `docs/entrega/presentacion.pptx`

Entregable exigido. Ausente hoy. El enunciado pide explícitamente: plan de implementación, hitos, supuestos, riesgos y racional de las decisiones técnicas.

- [ ] **Step 1:** Usar la skill `anthropic-skills:pptx`.
- [ ] **Step 2: Guion sugerido** — problema y alcance; arquitectura; ingestión y evidencia; recuperación; los dos flujos y el router; **la decisión de abstenerse y por qué es el punto fuerte**; evaluación y resultados; riesgos y limitaciones; hitos y siguientes pasos.
- [ ] **Step 3:** Incluir capturas reales de `docs/screenshots/` y de las trazas de Langfuse. Ninguna cifra que no salga de una ejecución registrada.

---

### Task 13: Guion de demo y ensayo

**Files:** Create `docs/entrega/guion-demo.md`; create `backend/src/infrastructure/adapters/inbound/api/routes/demo.py`; test `backend/tests/test_demo_cases_api.py`

- [ ] **Step 1: Implementar `GET /api/v1/demo/cases`, que la spec exige y no existe.** Es la única de las diez capacidades HTTP de la sección 8 de la spec que falta, y es justo la que sostiene una demo determinista. Debe servir los cinco relatos del enunciado más las preguntas documentales seleccionadas, leídos del golden de partición `dev` — **nunca** de una lista codificada a mano en el adaptador, y **nunca** exponiendo `expected_output` ni `expected_evidence_ids`, que filtrarían la referencia al sistema evaluado.
- [ ] **Step 2: Escribir primero el test que falle** si la respuesta incluye cualquier campo de referencia, y el que falle si el endpoint devuelve casos de la partición de reserva.
- [ ] **Step 3:** Conectar el frontend al endpoint para poblar las sugerencias del empty state con casos reales, sustituyendo las sugerencias actuales.
- [ ] **Step 4:** Escribir `docs/entrega/guion-demo.md`: guion determinista para 30-45 min con los cinco siniestros en orden, más 3-4 preguntas documentales.
- [ ] **Step 5:** Para cada caso, dejar escrito qué debe ocurrir en pantalla y qué se explica mientras ocurre. El momento clave del guion es el siniestro 2 o el 3: explicar **por qué abstenerse es la respuesta correcta** y enseñar la regla y la página del manual que lo sostienen.
- [ ] **Step 6:** Plan de contingencia: qué hacer si OpenAI, Qdrant o Langfuse fallan en vivo.
- [ ] **Step 7:** Ensayar el recorrido completo desde checkout limpio y cronometrarlo.

---

## Self-review de este plan

**Cobertura de la spec:** las diez capacidades HTTP de la sección 8 quedan cubiertas — nueve ya existen y `GET /api/v1/demo/cases` se añade en Task 13. El dimensionado del golden de la sección 9 se recoge en Task 5. La evaluación en inglés que exige la sección 6 se cubre en Tasks 4 y 7. Los criterios de salida de la sección 12, incluida la fila «Casos de entrevista» («no se exige inventar una conclusión definitiva»), se cubren en Tasks 3 y 4.

**Cobertura del enunciado:** los tres entregables tienen tarea propia (Task 11 documento, Task 12 presentación, Tasks 0-10 código). Los cinco siniestros tienen tests (Task 3) y anotación golden (Task 4). La "basic evaluation" queda cubierta por Task 5. La exposición en vivo, por Task 13.

**Cobertura de las tareas pendientes del plan anterior:** T6 → Task 3; T7 → Task 6; T8 → Task 7; T9 → Task 8; **T10 → Task 10 Step 5** (sólo queda la mitad frontend); T11 → Task 9; T12/T13 → Task 10; T14 → Task 13; T15 → Tasks 5, 11, 12. T4/T5 (contenido de golden y matriz) → Tasks 1, 2, 4, 5.

**Riesgo principal:** el plazo. Con 1-2 días, Tasks 6, 7, 9 y 10 son las primeras candidatas a caer. La línea de corte del encabezado dice qué se sacrifica y en qué orden, y Task 11 recoge lo sacrificado como limitación declarada.

**Riesgo secundario:** las tres PARADAS de adjudicación humana (Task 1 Step 9, Task 2 Step 7, Task 4 Step 3) son bloqueantes por diseño. Conviene agruparlas para no fragmentar la atención del usuario: la del catálogo de circunstancias puede resolverse en la misma sesión que la de la matriz.

**Riesgo de fondo, heredado:** este plan se apoya en verificación propia, no en los handoffs. Cualquier agente que lo ejecute debe repetir el mismo escepticismo: los documentos de traspaso de este repositorio han demostrado ir por detrás del código en al menos tres puntos comprobados.
