# Allianz RAG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar el asistente local de la prueba de Allianz con citas verificables, consulta documental, análisis de siniestros, modo automático y evaluación reproducible.

**Architecture:** Backend y frontend independientes en un repositorio Git local. Dominio y aplicación sin frameworks; adaptadores LangGraph reutilizan los mismos casos de uso desde API, CLI y experimentos. Langfuse y Ragas gestionan evaluación y revisión sin un runner o laboratorio duplicado.

**Tech Stack:** Python 3.14, uv, Ruff, Pyright, pytest, FastAPI/Pydantic 2, LangGraph, pypdf, Docling, Qdrant, OpenAI SDK, Langfuse, Ragas, React/TypeScript/Vite/pnpm, Tailwind, shadcn/ui y PDF.js.

**Spec:** [Especificación aprobada](../specs/2026-08-31-allianz-rag-design.md), con los tres anexos enlazados allí. Aprobada por el usuario el 31 de agosto de 2026.

## Global Constraints

- «No se añadirá `cicos/` debajo de `src/` ni un directorio `presentation` separado de infraestructura.»
- «Backend y frontend tendrán dependencias, lockfiles, comandos y pruebas propios.»
- «Aplicación y dominio no importarán LangGraph, FastAPI o los SDKs de proveedores.»
- «Los modos explícitos omitirán el router y no serán cambiados silenciosamente.»
- «El SDK de Langfuse ejecutará los experimentos mediante `run_experiment` contra datasets registrados en nuestra instancia local.»
- «No habrá un runner paralelo.»
- «Los cinco originales estarán en desarrollo.»
- «Paráfrasis, traducciones y variantes de una familia no cruzarán particiones.»
- «Los servicios se publicarán solo en localhost.»
- «Los secretos permanecerán fuera de Git y del frontend».
- «Los POST devolverán JSON o SSE mediante `stream: true`, reutilizando el mismo resultado final.»
- «No hay llamadas pagadas realizadas durante esta fase de especificación.» Al ejecutar se registrará el consumo real; una prueba con doble de proveedor no acredita una llamada real.
- Python 3.14 estándar; las dependencias se resolverán y bloquearán con uv. No degradar versiones sin documentar una incompatibilidad verificada.
- Mantener Git local: no crear remoto, publicar ni subir fuentes a GitHub en esta fase.

---

## Organización, comandos y dependencias

Este plan recorre un único producto en entregas comprobables. Las tareas de ingesta y curación producen artefactos utilizables por CLI antes de que exista el frontend. Los experimentos de selección dependen de la referencia congelada, no al revés. La interfaz se construye contra OpenAPI y consume resultados ya definidos.

Todos los comandos parten de la raíz del repositorio salvo que indiquen otra cosa. Los paths son relativos a ella. Los paquetes Python son `domain`, `application` e `infrastructure` bajo `backend/src`; `bootstrap.py` es un módulo de composición. Los SDKs y sus tipos permanecen en infraestructura. Los ejemplos de pruebas definen comportamientos, no respuestas verdaderas de seguros.

Cada tarea de código sigue RED → implementación mínima → GREEN → lint/tipos → revisión → commit limitado a sus archivos. Los bloques muestran el núcleo de comportamiento; los imports, modelos, errores y firmas a los que aluden se definen en la tarea indicada. Los pasos de datos se revisan contra la fuente y no se convierten en tests que se autovalidan.

Comprobación común que se crea en T1:

```bash
make check-backend
```

Ejecutará `uv run --project backend ruff check backend`, `uv run --project backend ruff format --check backend`, `uv run --project backend pyright --project backend` y `uv run --project backend pytest backend/tests`. Toda verificación nueva se ejecutará también de forma focalizada. Las integraciones que necesitan servicios o modelos reales se marcarán explícitamente y no se contarán como aprobadas cuando se omitan.

Dependencias observadas: uv 0.11.26, Python 3.14.6 instalado, Node 26.8.1 y pnpm 11.19.0. No se encontró Docker, Docker Desktop, OrbStack o Colima en las ubicaciones comprobadas. T1–T4 no requieren motor de contenedores ni claves; T5 debe comprobar disponibilidad real antes de declarar servicios listos.

### Mapa de responsabilidades

| Archivos/directorios | Responsabilidad y tarea introductoria |
| --- | --- |
| `domain/models/document.py`, `application/ports/*/inspect_manual.py`, `source_inspector.py` | Identidad y validación de la fuente; T1. |
| `domain/models/evidence.py`, `document_parser/`, `evidence_repository/` | Elementos originales, extracción y persistencia; T2–T3. |
| `application/services/chunking.py`, `infrastructure/config/profiles.py` | Segmentación y compatibilidad de perfiles; T4. |
| `compose.yaml`, `ops/langfuse/`, `ops/local.env.example` | Servicios y configuración local; T5. |
| `adapters/inbound/api/`, `application/services/citations.py` | Fuente registrada y citas; T6. |
| `adapters/outbound/retriever/`, `embedding_provider/` | Índices y recuperación densa, léxica e híbrida; T7. |
| `application/models/query.py`, `question_workflow/`, `language_model/` | Contratos de consulta y recorrido documental; T8. |
| `adapters/outbound/evaluation/`, `docs/evaluation/` | Esquema, integración, métricas, calibración y publicación; T9–T12. |
| `domain/rules/`, `domain/models/claim.py`, `decision.py` | Reglas y resultados del accidente; T13–T14. |
| `application/services/visual_context.py`, `reranking.py` | Mejoras experimentales de contexto; T15. |
| `query_workflow/`, `application/services/routing.py` | Automático con selección explícita de ruta; T16. |
| `adapters/inbound/api/schemas/`, `routes/queries.py`, `streaming.py` | API de los tres modos y errores; T17. |
| `frontend/src/api/`, `features/assistant/`, `features/manual/` | Producto y visor; T18–T19. |
| `docs/results/`, `docs/presentation/`, Dockerfiles y README | Selección final, operación y entrega; T20–T21. |

En esa tabla, `adapters/` se refiere a `backend/src/infrastructure/adapters/`. Las listas Files de cada tarea usan rutas completas relativas al repositorio.

## Task 1: Auditoría de la fuente y primer comando reproducible

**Files:** Crear `.gitignore`, `Makefile`, `README.md`, `backend/pyproject.toml`, `backend/uv.lock`, `backend/.python-version`; crear `backend/src/domain/models/document.py`, `backend/src/application/ports/inbound/inspect_manual.py`, `backend/src/application/ports/outbound/source_inspector.py`, `backend/src/application/use_cases/inspect_manual_use_case.py`, `backend/src/infrastructure/adapters/outbound/source_inspector/pypdf_source_inspector.py`, `backend/src/infrastructure/adapters/inbound/cli/main.py`, `backend/src/bootstrap.py` y los `__init__.py` necesarios. Pruebas: `backend/tests/test_inspect_manual.py`, `backend/tests/test_cli.py`.

**Interfaces:** `DocumentManifest(document_id: str, sha256: str, filename: str, page_count: int)` es una dataclass inmutable. `SourceInspector.inspect(source: Path) -> DocumentManifest`. `InspectManual.execute(source: Path, expected_sha256: str | None = None) -> DocumentManifest`. `SourceInspectionError` y `SourceIntegrityError` se definen en el módulo del modelo. `build_inspect_manual() -> InspectManual`; CLI `main(argv: Sequence[str] | None = None) -> int`.

- [ ] Configurar setuptools con `package-dir = {"" = "src"}`, `py-modules = ["bootstrap"]` y descubrimiento de los tres paquetes. Script `allianz = "infrastructure.adapters.inbound.cli.main:main"`. Añadir pypdf y grupo dev pytest/Ruff/Pyright; fijar Python 3.14 y lockfile. Ignorar `.env*` salvo ejemplos, `.venv`, caches, builds, `.DS_Store`, `.worktrees/` y `data/` generado; no ignorar fixtures de pruebas ni documentos Markdown.
- [ ] Escribir primero una prueba con PDF sintético válido y hash esperado incorrecto:

```python
def test_rejects_an_unexpected_document(tmp_path):
    from pypdf import PdfWriter
    from bootstrap import build_inspect_manual
    from domain.models.document import SourceIntegrityError
    import pytest

    source = tmp_path / "manual.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(source)
    with pytest.raises(SourceIntegrityError):
        build_inspect_manual().execute(source, expected_sha256="0" * 64)
```

- [ ] Ejecutar `uv run --project backend pytest backend/tests/test_inspect_manual.py -q`; observar el fallo por ausencia del comportamiento. Añadir pruebas de hash/páginas correctos, bytes no PDF, archivo inexistente, PDF cifrado rechazado, JSON CLI y exit code 2 sin traceback para errores de entrada.
- [ ] Implementar inspección leyendo bytes una vez, calculando SHA-256 y pasando esos mismos bytes a `PdfReader(BytesIO(data))`; rechazar cifrado y cero páginas. `document_id = "sha256:" + digest`; no inferir edición, título o paginación impresa. El caso de uso comprobará el hash antes de devolver el manifiesto. Núcleo:

```python
manifest = self.inspector.inspect(source)
if expected_sha256 is not None and manifest.sha256 != expected_sha256:
    raise SourceIntegrityError("The source does not match the expected SHA-256")
return manifest
```

- [ ] Crear CLI argparse `inspect-manual SOURCE [--expected-sha256 HASH]`: JSON del manifiesto a stdout, errores legibles a stderr y código 2. Comprobar entrada, sin escribir ni modificar el manual. Ejecutar `make check-backend` y `uv build --project backend`; comprobar que el wheel incluye los paquetes y `bootstrap.py`.
- [ ] Ejecutar contra el original:

```bash
uv run --project backend allianz inspect-manual /Users/aoc/Downloads/Manual-cide-ascide-y-cicos.pdf --expected-sha256 b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344
```

Esperado: hash exacto, `page_count: 111`, salida 0. Documentar que esto verifica identidad/lectura, no extracción de tablas ni respuestas RAG. Revisar y commit `feat: add reproducible manual source inspection` con los archivos de esta tarea.

## Task 2: Extracción baseline y registro inmutable de evidencias

**Files:** Crear `backend/src/domain/models/evidence.py`; `backend/src/application/ports/outbound/document_parser.py`, `evidence_repository.py`; `backend/src/application/ports/inbound/ingest_document.py`; `backend/src/application/use_cases/ingest_document_use_case.py`; `backend/src/infrastructure/adapters/outbound/document_parser/pypdf_parser.py`; `backend/src/infrastructure/adapters/outbound/evidence_repository/filesystem_repository.py`; `backend/tests/test_baseline_ingestion.py`. Modificar CLI y bootstrap de T1.

**Interfaces:** `PageEvidence(evidence_id: str, document_hash: str, pdf_page: int, text: str, printed_label: str | None, image_path: str | None, regions: tuple[tuple[float, float, float, float], ...])`; `Extraction(manifest: DocumentManifest, pages: tuple[PageEvidence, ...], parser: str, warnings: tuple[str, ...])`. `DocumentParser.parse(source: Path) -> Extraction`. `EvidenceRepository.publish(extraction: Extraction) -> Path`, `get(evidence_id: str) -> PageEvidence`. `IngestDocument.execute(source: Path) -> Extraction`.

- [ ] Escribir `test_keeps_empty_pages` con un PDF de dos páginas en blanco y comprobar `pdf_page == [1, 2]`, texto vacío conservado y avisos, no descarte de páginas. Ejecutar `uv run --project backend pytest backend/tests/test_baseline_ingestion.py -q` y observar RED.
- [ ] Implementar la enumeración física completa; el baseline no inventa coordenadas ni etiquetas impresas:

```python
for number, page in enumerate(reader.pages, start=1):
    text = page.extract_text() or ""
    evidence_id = f"{manifest.document_id}:page:{number}"
    pages.append(PageEvidence(evidence_id, manifest.sha256, number, text, None, None, ()))
```

- [ ] Guardar manifest y páginas JSONL en un directorio temporal del mismo filesystem; validar count/hash; publicar mediante rename a `data/extractions/{hash}/{parser-version}/`. Si existe una publicación distinta bajo esa identidad, rechazarla; no sobreescribir. Probar excepción a mitad de escritura: no debe aparecer publicación completa. Añadir comando `allianz ingest SOURCE --parser pypdf --output data/extractions`.
- [ ] Ejecutar el comando sobre las 111 páginas y revisar las páginas PDF 32 y 101 contra los renders originales; registrar pérdidas, sin declarar extraída la matriz. GREEN + `make check-backend`; commit `feat: preserve page evidence during baseline ingestion`.

## Task 3: Extracción estructurada y evidencia visual conservada

**Files:** Crear `backend/src/infrastructure/adapters/outbound/document_parser/docling_parser.py`, `page_renderer.py`; `backend/tests/integration/test_docling_parser.py`; `docs/ingestion/parser-comparison.md`. Modificar modelo de evidencia y selector de parser de T2.

**Interfaces:** `DoclingParser.parse(source: Path) -> Extraction` implementa el puerto de T2. `render_page(source: Path, pdf_page: int, destination: Path) -> Path`. Añadir a PageEvidence elementos opcionales de sección/tipo y mantener compatibilidad de IDs de página; las regiones de elementos tienen IDs subordinados a la fuente, nunca al chunk.

- [ ] Escribir una integración que cargue una página con tabla y otra escaneada del documento real mediante una ruta configurada para tests de integración. Comprobar que el inventario sigue incluyendo todas las páginas, y que un fallo OCR queda declarado. Ejecutar RED con `uv run --project backend pytest backend/tests/integration/test_docling_parser.py -q`.
- [ ] Resolver Docling y el renderer en un grupo `ingestion`, bloquear dependencias y comprobar imports en Python 3.14. Núcleo de conversión oficial, contrastado con la versión instalada:

```python
from docling.document_converter import DocumentConverter

converted = DocumentConverter().convert(source)
document = converted.document
markdown = document.export_to_markdown()
```

Recorrer elementos y procedencia de `document`, preservando cabeceras/notas y convirtiendo coordenadas a la convención de página visible; no deducir bounding boxes a partir del texto Markdown.
- [ ] Renderizar el original y revisar página 32 y matriz de página 101 a resolución legible. Persistir original, elementos y diagnóstico; no sustituir la imagen por un resumen de IA. Probar rotación/recorte con un PDF fixture y coordenadas conocidas.
- [ ] Comparar inventario de ambos parsers, documentar pérdidas y publicar solo el artefacto completo. GREEN + controles de backend; commit `feat: add structured extraction with original page evidence`.

## Task 4: Chunking y perfiles compatibles con los índices

**Files:** Crear `backend/src/application/models/retrieval.py`, `backend/src/application/services/chunking.py`, `backend/src/infrastructure/config/profiles.py`, `backend/configs/baseline.yaml`, `backend/configs/structured.yaml`, `backend/tests/test_chunking_profiles.py`.

**Interfaces:** `Chunk(chunk_id: str, text: str, evidence_ids: tuple[str, ...])`; `chunk_fixed(pages: Sequence[PageEvidence], size: int, overlap: int) -> tuple[Chunk, ...]`; `chunk_sections(pages: Sequence[PageEvidence], max_size: int) -> tuple[Chunk, ...]`. `IndexSignature(document_hash: str, parser: str, chunker: str, embedding_model: str, dimensions: int, lexical_language: str)`; `assert_compatible(actual: IndexSignature, expected: IndexSignature) -> None` lanza `IncompatibleIndexError`.

- [ ] Escribir y ejecutar RED para un cambio de dimensiones o idioma léxico que pretenda reutilizar el mismo índice:

```python
def test_embedding_dimension_change_invalidates_index():
    from dataclasses import replace
    from application.models.retrieval import IndexSignature, IncompatibleIndexError, assert_compatible
    import pytest

    original = IndexSignature("a" * 64, "pypdf", "fixed", "embedding-test", 3, "spanish")
    with pytest.raises(IncompatibleIndexError):
        assert_compatible(original, replace(original, dimensions=4))
```

- [ ] Implementar validación `size > 0`, `0 <= overlap < size`; conservar IDs de evidencia a través del corte. Derivar `chunk_id` de contenido, fuentes y configuración mediante JSON canónico + SHA-256. Nunca utilizar chunk IDs como verdad de evaluación.
- [ ] Validar YAML con Pydantic en infraestructura; rechazar claves desconocidas, perfiles incompatibles y rutas fuera del catálogo. Serializar firma completa; la comparación es igualdad estructural, no solo del nombre del índice. Probar que una nota de tabla no se separa de sus cabeceras en el chunker estructurado.
- [ ] `uv run --project backend pytest backend/tests/test_chunking_profiles.py -q`, controles comunes y commit `feat: add source-aware chunks and validated retrieval profiles`.

## Task 5: Qdrant y Langfuse locales con comprobación de compatibilidad

**Files:** Crear `compose.yaml`, `ops/langfuse/compose.upstream.yaml`, `ops/langfuse/SOURCE.md`, `ops/local.env.example`, `backend/src/infrastructure/adapters/inbound/cli/doctor.py`, `backend/tests/test_doctor.py`, `docs/operations/local-services.md`. Modificar Makefile y dependencias necesarias.

**Interfaces:** `check_environment() -> dict[str, bool | str]` informa binarios/servicios sin secretos. CLI `allianz doctor` devuelve código distinto de 0 si faltan servicios requeridos para la operación elegida. La comprobación no invoca un LLM.

- [ ] Test RED con ausencia simulada de `docker`: `check_environment()["containers_available"] is False`; no afirmar que el sistema está listo. Ejecutar `uv run --project backend pytest backend/tests/test_doctor.py -q`.
- [ ] Obtener la configuración oficial de Langfuse para self-hosting y registrar el commit/tag exacto en SOURCE.md. Mantener sus servicios dependientes y añadir overrides locales, puertos en `127.0.0.1`, volúmenes persistentes y secretos desde archivo ignorado. La selección del digest/tag es una medición de instalación: no usar `latest` como artefacto de entrega.
- [ ] Con un motor de contenedores disponible, validar y arrancar:

```bash
docker compose --env-file ops/local.env config --quiet
docker compose --env-file ops/local.env up -d
uv run --project backend allianz doctor
```

Comprobar salud real, reinicio con persistencia y consumo conjunto. Si falta el motor, avanzar en tareas sin servicios y registrar esta integración como no ejecutada; no instalar una aplicación de sistema ni cambiar su configuración sin resolver el acceso necesario.
- [ ] Instalar SDKs y comprobar nativamente un dataset técnico de dos items en Langfuse, un score por item y comparación de dos runs. No usar el golden set ni llamadas pagadas. Comprobar `get_dataset` con versión contra la API instalada; documentar el comportamiento, incluyendo esquema no versionado. GREEN, controles y commit `feat: add local retrieval and evaluation services`.

## Task 6: Catálogo de fuente y citas navegables por API

**Files:** Crear `backend/src/application/services/citations.py`, `backend/src/infrastructure/adapters/inbound/api/app.py`, `routes/manual.py`, `schemas/evidence.py`, `backend/tests/test_manual_api.py`. Modificar bootstrap, dependencias y Makefile.

**Interfaces:** `resolve_citations(ids: Sequence[str], repository: EvidenceRepository) -> tuple[PageEvidence, ...]`; `create_app() -> FastAPI`. Definir `RegisteredSource(path: Path, manifest: DocumentManifest)` en el adaptador y un catálogo `dict[str, RegisteredSource]` cargado desde publicaciones verificadas. GET manual, PDF por versión, evidencia por ID y salud según el anexo de API. El PDF servido proviene de una ruta registrada por hash. El DTO HTTP convierte las tuplas de regiones de dominio a objetos con campos `x0`, `y0`, `x1`, `y1`, todos normalizados.

- [ ] Prueba RED: una versión inexistente del PDF devuelve 404, nunca el documento activo; un ID con traversal no abre archivos externos. Usar `TestClient` con catálogo temporal y PDF fixture.
- [ ] Implementar la resolución mediante búsqueda en registro, sin concatenar el input a una ruta de disco. Núcleo de comprobación:

```python
record = catalog.get(version)
if record is None:
    raise HTTPException(status_code=404, detail="Document version not found")
return FileResponse(record.path, media_type="application/pdf")
```

`catalog` es un mapping interno de hashes a registros fuente creados por la ingesta; no lo alimenta el LLM.
- [ ] `/health/live` devuelve vida del proceso. `/health/ready` devuelve 503 si falta el índice requerido; el catálogo solo no implica RAG listo. Probar que no hay llamadas a proveedor en salud.
- [ ] Verificar API, páginas 1 y 111, respuesta 404 ante evidencia ausente, controles comunes y commit `feat: expose registered manual evidence and versioned PDF`.

## Task 7: Recuperación densa, BM25 e híbrida en Qdrant

**Files:** Crear `backend/src/application/ports/outbound/embedding_provider.py`, `retriever.py`; `backend/src/infrastructure/adapters/outbound/embedding_provider/openai_embedding_provider.py`; `backend/src/infrastructure/adapters/outbound/retriever/qdrant_retriever.py`, `index_builder.py`; `backend/tests/integration/test_retrieval.py`.

**Interfaces:** `EmbeddingProvider.embed(texts: Sequence[str]) -> Awaitable[tuple[tuple[float, ...], ...]]`; `RetrievalRequest(text: str, limit: int, mode: Literal["dense", "bm25", "hybrid"])`; `Retriever.retrieve(request: RetrievalRequest) -> Awaitable[tuple[Chunk, ...]]`. `build_index(chunks: Sequence[Chunk], signature: IndexSignature) -> Awaitable[str]` publica una colección validada y devuelve su nombre.

- [ ] Test RED con corpus técnico pequeño y vectores fixture: BM25 encuentra un identificador literal; densa encuentra el concepto esperado; híbrida devuelve IDs válidos sin duplicados. Otro test rechaza firma incompatible. Los fixtures no contienen etiquetas del manual.
- [ ] Añadir named vectors `dense` y `bm25`, y RRF nativo en la consulta híbrida:

```python
result = await client.query_points(
    collection_name=collection,
    prefetch=[
        models.Prefetch(query=dense_query, using="dense", limit=limit),
        models.Prefetch(query=sparse_query, using="bm25", limit=limit),
    ],
    query=models.FusionQuery(fusion=models.Fusion.RRF),
    limit=limit,
    with_payload=True,
)
```

Verificar con la versión instalada cómo calcular BM25 localmente y fijar idioma español; probar negaciones y siglas. No activar inferencia cloud. El adaptador de embeddings utilizará el SDK OpenAI y preservará orden/dimensiones, con caché por texto y modelo.
- [ ] Indexar por lotes en colección nueva; comprobar counts y firma antes de publicar. Un fallo no cambia la colección activa. Registrar toda llamada real y reintento. Probar con transporte simulado respuestas inválidas y rate limits; la integración real exige clave configurada fuera del chat.
- [ ] Ejecutar pruebas y un smoke de retrieval real sin juez; registrar contexto obtenido, sin seleccionar aún ganador. Commit `feat: add interchangeable dense lexical and hybrid retrieval`.

## Task 8: Consulta documental con LangGraph y proveedor tipado

**Files:** Crear `backend/src/application/models/query.py`, `backend/src/application/ports/inbound/answer_question.py`, `backend/src/application/ports/outbound/question_workflow.py`, `language_model.py`; `backend/src/application/use_cases/answer_question_use_case.py`; `backend/src/application/services/question_answering.py`; `backend/src/infrastructure/adapters/outbound/question_workflow/langgraph_workflow.py`, `language_model/openai_language_model.py`; `backend/tests/test_question_workflow.py`.

**Interfaces:** `QueryInput(text: str, language: Literal["es", "en"])`; `AnswerBlock(text: str, evidence_ids: tuple[str, ...])`; `QuestionAnswer(status: Literal["answered", "partial", "insufficient_evidence", "out_of_scope"], blocks: tuple[AnswerBlock, ...])`; `ContextEvidence(evidence_id: str, text: str, source: PageEvidence, delivery: Literal["text", "image", "rule"])`; `QueryExecution(result: QuestionAnswer, context: tuple[ContextEvidence, ...], trace_id: str | None)`. `AnswerQuestion.execute(query: QueryInput) -> Awaitable[QueryExecution]`; `QuestionWorkflow.run(query: QueryInput) -> Awaitable[QueryExecution]`. `ContextEvidence.text` es exactamente el fragmento entregado, no el texto completo de la página fuente; en imágenes/rules se registra el payload efectivo junto con sus artefactos.

- [ ] RED con un proveedor doble que devuelve una cita no suministrada; el sistema no la entrega como cita válida. Definir doble en `backend/tests/fakes.py` y otro que falle técnicamente; ese fallo no debe convertirse en `insufficient_evidence`.
- [ ] Implementar los nodos `retrieve`, `generate`, `validate` en infraestructura; los servicios de aplicación reciben puertos, no tipos LangGraph. Estado tipado y límites de ejecución. El proveedor usa salida estructurada:

```python
response = await client.responses.parse(
    model=model_id,
    input=messages,
    text_format=AnswerSchema,
    store=False,
)
if response.output_parsed is None:
    raise ModelOutputError("No parsed answer returned")
```

`AnswerSchema` se define con Pydantic en el adaptador y se convierte a `QuestionAnswer`; `ModelOutputError` es un error de aplicación. Manejar refusal, incompleto, timeout y schema inválido sin rellenar una respuesta ficticia. `messages` contiene instrucciones versionadas y contexto delimitado como datos.
- [ ] Integrar prompts de Langfuse por versión concreta y traza de nodos/proveedor sin doble conteo. Guardar contenido efectivo en manifiesto. La respuesta solo puede referenciar evidencia registrada y recibida; los checks semánticos se medirán en evaluación, no se asumirán infalibles.
- [ ] Exponer CLI `allianz answer --text TEXT --profile PROFILE`; devolver respuesta y metadatos sin claves. GREEN, smoke real cuando haya clave y commit `feat: implement grounded document questions with LangGraph`.

## Task 9: Esquema de referencia y protección de particiones

**Files:** Crear `backend/src/infrastructure/adapters/outbound/evaluation/golden_schema.py`, `release_validation.py`, `backend/tests/test_golden_integrity.py`, `docs/evaluation/golden-schema.json`, `docs/evaluation/coverage-matrix.md`.

**Interfaces:** Validar los campos nativos de items Langfuse: `input`, `expected_output`, `metadata`. `input` solo contiene texto, idioma y aclaraciones del usuario. `expected_output` contiene referencia, decisiones esperadas, requisitos, alternativas, hechos prohibidos y paquetes de evidencia. `metadata` contiene `case_id`, `family_id`, `partition`, `review_status`, procedencia, idioma e intención esperada. `check_family_splits(assignments: Sequence[tuple[str, str]]) -> None` lanza `ValueError` ante contaminación; `validate_release(items: Sequence[dict[str, object]]) -> None` rechaza esquema inválido o revisiones no admitidas.

- [ ] Escribir y ejecutar RED:

```python
def test_family_cannot_cross_development_and_holdout():
    from infrastructure.adapters.outbound.evaluation.release_validation import check_family_splits
    import pytest

    with pytest.raises(ValueError, match="family"):
        check_family_splits([("family-1", "development"), ("family-1", "holdout")])
```

- [ ] Implementar modelos Pydantic de validación de la referencia, no una copia de `Dataset` o `DatasetItem`. Exportar JSON Schema. Validador de familias:

```python
seen: dict[str, str] = {}
for family_id, partition in assignments:
    if family_id in seen and seen[family_id] != partition:
        raise ValueError(f"family {family_id} crosses partitions")
    seen[family_id] = partition
```

- [ ] Probar que `quarantined`, revisión incompleta, evidencia inexistente y respuesta esperada introducida dentro de `input` impiden publicación. Escribir cobertura del manual por tema/tipo de dificultad, sin inventar casos aprobados. Los cinco ejemplos originales se registrarán en desarrollo con texto fiel.
- [ ] GREEN + controles comunes; commit `feat: validate golden references and dataset partitions`.

## Task 10: Experimentos nativos Langfuse y conexión con Ragas

**Estado de ejecución (1 de septiembre de 2026):** runner nativo cerrado. El aislamiento de entrada,
la serialización, el evaluador FactualCorrectness nativo y la llamada nativa a
`DatasetClient.run_experiment` están implementados y comprobados contra
Ragas 0.4.3/Langfuse 4.15.1; el runner inyecta el cliente Langfuse para
tests sin monkeypatching global, valida `dataset_name`/`dataset_version`/
`profile_name` no blank, y usa `ALLIANZ_LANGFUSE_MAX_CONCURRENCY` (default 4)
en lugar del default 50 del SDK. Faltan la publicación/validación de releases
y un smoke nativo contra un dataset real registrado en Langfuse.

**Files:** Crear `backend/src/infrastructure/adapters/outbound/evaluation/langfuse_experiments.py`, `ragas_evaluators.py`, `dataset_releases.py`, `backend/tests/test_evaluation_input_boundary.py`, `backend/tests/integration/test_langfuse_experiments.py`. Modificar CLI y configuración.

**Interfaces:** `run_question_experiment(dataset_name: str, dataset_version: str, profile_name: str) -> None` carga un dataset registrado, verifica manifiesto y llama a su `run_experiment`. El callback usa el `DatasetItem` nativo; el adaptador devuelve una representación serializable de `QueryExecution`. No se filtra `expected_output` a `QueryInput`.

- [x] RED: un item contiene una cadena centinela solo en referencia y metadatos; el caso de uso espía no debe recibirla en ningún campo. El spy se define en `test_evaluation_input_boundary.py`, conserva los QueryInput recibidos y devuelve una QuestionAnswer técnica con contexto vacío, sin pasarla por resultado del manual.
- [x] Implementar el callback con selección explícita de entrada:

```python
async def task(*, item, **kwargs):
    query = QueryInput(text=item.input["text"], language=item.input["language"])
    execution = await answer_question.execute(query)
    return serialize_execution(execution)

result = dataset.run_experiment(name=run_name, task=task, evaluators=evaluators)
```

`serialize_execution` se define en el mismo adaptador: devuelve `result`, `answer_text` (bloques unidos por dos saltos de línea), `context` y `trace_id`. Conserva salida/contexto realmente entregado; no envía las páginas completas por comodidad. Usar la firma de la versión fijada para concurrencia y evaluadores por run. La integración con un dataset técnico debe demostrar aislamiento de errores y comparación en UI; una lista Python sola no cumple ese control.
- [x] Conectar FactualCorrectness mediante la API nativa comprobada. El adaptador usa las
APIs públicas instaladas, recibe únicamente `output.answer_text` y
`expected_output.reference`, y está probado con un doble sin llamadas pagadas:

```python
from langfuse import Evaluation
from ragas.metrics.collections import FactualCorrectness

scorer = FactualCorrectness(llm=judge_llm, mode="f1", atomicity="high", coverage="high")
async def factual_evaluator(*, output, expected_output, **kwargs):
    score = await scorer.ascore(response=output["answer_text"], reference=expected_output["reference"])
    return Evaluation(name="factual_f1", value=score.value)
```

`judge_llm` se construye con `ragas.llms.llm_factory` y modelo explícito. Si la versión instalada no ofrece esa API, registrar la incompatibilidad y adaptar al método público soportado con prueba; no mezclar imports privados legacy sin comprobarlos.
- [ ] Implementar exportación de items y resultados usando SDK/APIs nativos; JSON canónico ordenado, esquema separado y SHA-256. Comparar contenido cargado con el manifiesto antes de ejecutar. Vaciar trazas al finalizar; si falla publicación, estado incompleto, no éxito. Ejecutar pruebas, smoke nativo y commit `feat: run native Langfuse experiments with Ragas evaluators`.

## Task 11: Métricas de evidencias, decisiones e ingeniería

**Estado de ejecución (1 de septiembre de 2026):** iniciada. Cobertura AND/OR,
precisión/recall de citas y coste por éxito están implementados y probados; faltan las
métricas de decisiones, las rúbricas Ragas y el catálogo operativo completo.

**Files:** Crear `backend/src/infrastructure/adapters/outbound/evaluation/domain_evaluators.py`, `run_metrics.py`, `backend/tests/test_evidence_metrics.py`, `backend/tests/test_run_metrics.py`, `docs/evaluation/metric-catalog.md`.

**Interfaces:** `coverage(requirements: Sequence[Sequence[frozenset[str]]], delivered: frozenset[str]) -> float | None`: requisitos externos AND, paquetes alternativos OR, y cada paquete exige todos sus miembros. `cost_per_success(total_cost: float, successes: int) -> float | None`. Evaluadores devuelven `langfuse.Evaluation`, no un tipo Score propio.

- [x] RED para la excepción ausente y el denominador vacío:

```python
def test_retrieving_rule_without_required_exception_is_not_sufficient():
    from infrastructure.adapters.outbound.evaluation.domain_evaluators import coverage

    requirement = [[frozenset({"rule", "exception"})]]
    assert coverage(requirement, frozenset({"rule"})) == 0.0
    assert coverage([], frozenset()) is None
```

- [x] Implementar la operación de conjuntos, usando `delivered` calculado a partir del contenido real y su alineación con evidencias revisadas. Un ID de página, por sí solo, no demuestra entrega de la frase o región requerida. Núcleo:

```python
if not requirements:
    return None
covered = sum(any(package <= delivered for package in alternatives) for alternatives in requirements)
return covered / len(requirements)
```

- [ ] Integrar validez/precisión/cobertura de citas, hechos inventados, condiciones omitidas, macro-F1 por decisión y router, abstenciones y errores críticos según el anexo. Usar rúbricas Ragas para soporte semántico y preguntas de aclaración; comparar enums y referencias de forma determinista. Los hechos se contrastan contra usuario y las reglas contra manual.
- [ ] Registrar latencia/consumo por etapas, p50/p95 con tamaño muestral, primer contenido útil, fallos y reintentos. Coste total dividido entre todos los éxitos: con coste 12 y 3 éxitos es 4 aunque haya intentos fallidos; con cero éxitos es no aplicable, no cero. Separar juez, ingesta e inferencia y caché fría/caliente.
- [ ] Ejecutar pruebas y catalogar fórmula, sentido, denominador, versión y límites de cada métrica. Commit `feat: add source-based and operational evaluation metrics`.

## Task 12: Generación, revisión y congelación del golden set

**Files:** Crear `backend/src/infrastructure/adapters/outbound/evaluation/testset_generation.py`, `reference_review.py`, `backend/tests/test_reference_review.py`, `docs/evaluation/dataset-card.md`, `docs/evaluation/judge-calibration.md`. Artefactos reales: `data/golden/releases/`, `data/golden/calibration/`; mantenerlos fuera de Git hasta comprobar que el paquete final solo contiene contenido autorizado y revisado.

**Interfaces:** `generate_candidates(evidence_ids: Sequence[str], count: int) -> None` produce items en el dataset de trabajo Langfuse mediante TestsetGenerator Ragas. `review_candidate(case_id: str) -> None` registra revisiones y discrepancias. `freeze_release(dataset_name: str, release_id: str) -> Path` exige validación T9 y exporta snapshot/manifiesto, sin editor paralelo.

- [ ] Test RED: `freeze_release` rechaza un caso con desacuerdo abierto aunque dos jueces coincidan en la respuesta. Test de revisión ciega: el payload de resolución independiente no contiene la etiqueta propuesta. Los dobles simulan SDK, no la veracidad del manual.
- [ ] Construir el generador sobre evidencias curadas. Mecanismo nativo:

```python
from ragas.testset import TestsetGenerator

generator = TestsetGenerator(llm=generator_llm, embedding_model=embedding_model, knowledge_graph=knowledge_graph)
testset = generator.generate(testset_size=batch_size)
```

Configurar idioma y distribución mediante las APIs de la versión instalada. Si los escenarios necesitan sintetizador específico, extender QuerySynthesizer; no crear un grafo de producción por el KG interno de generación. Importar candidatos como items nativos con `review_status: draft`.
- [ ] Generar un piloto pequeño, revisar cada caso contra el PDF original y corregir el procedimiento antes de ampliar. Conservar resoluciones independientes, revisión adversarial y adjudicación; registrar cada revisor como modelo/persona según corresponda. No establecer una respuesta por votación. Repetir por lotes reanudables hasta cubrir la matriz, aproximadamente 70 casos, sin sacrificar calidad para completar el número.
- [ ] Comprobar por separado las 324 celdas y notas originales mediante transcripciones independientes antes de utilizarlas como referencia. Crear un conjunto de calibración de jueces con errores deliberados identificados: intercambio de partes, excepción omitida, cita irrelevante y falsa certeza. Ejecutar y analizar detección de esos errores; no corregir etiquetas verdaderas para mejorar una puntuación.
- [ ] Publicar los casos admitidos, separar familias 50/20 orientativo, congelar reserva antes de comparar candidatos y verificar hashes contra Langfuse. Documentar cobertura, exclusiones, revisiones no humanas y limitaciones. Ejecutar `allianz golden validate --release RELEASE` y `allianz golden freeze --dataset DATASET --release RELEASE`; ambos comandos se implementan en esta tarea y no publican si quedan discrepancias.
- [ ] Revisar dataset card y calibración con las evidencias registradas. Commit de código/documentación `feat: curate and freeze audited reference datasets`; no afirmar que el conjunto está completo antes de ejecutar realmente esta tarea.

## Task 13: Tabla y reglas deterministas con requisitos explícitos

**Estado de ejecución (1 de septiembre de 2026):** iniciada. El guard de matriz y el
primer filtro de aplicabilidad están implementados y probados. La matriz 18×18 y su
artefacto auditado no existen todavía, por lo que esta tarea no está cerrada.

**Files:** Crear `backend/src/domain/models/claim.py`, `decision.py`, `backend/src/domain/rules/applicability.py`, `cide_matrix.py`, `backend/tests/test_cide_matrix.py`, `backend/tests/test_applicability.py`; artefacto revisado `data/rules/cide-matrix.json` con manifiesto de fuentes.

**Interfaces:** `MatrixCell(a: int, b: int, outcome: str, evidence_ids: tuple[str, ...])`; `MatrixLookup(status: Literal["resolved", "undetermined"], cell: MatrixCell | None)`. `lookup_matrix(cells: Mapping[tuple[int, int], MatrixCell], a: int | None, b: int | None, prerequisites_confirmed: bool) -> MatrixLookup`. Las conclusiones del manual proceden del artefacto revisado T12, no de valores asumidos en el código.

- [x] RED para requisitos desconocidos, independientemente del contenido de la celda:

```python
def test_matrix_does_not_decide_without_confirmed_prerequisites():
    from domain.rules.cide_matrix import lookup_matrix

    result = lookup_matrix({}, a=1, b=2, prerequisites_confirmed=False)
    assert result.status == "undetermined"
    assert result.cell is None
```

- [x] Implementar el guard antes de cualquier acceso; no inferir checkbox desde una narración:

```python
if not prerequisites_confirmed or a is None or b is None:
    return MatrixLookup(status="undetermined", cell=None)
cell = cells.get((a, b))
return MatrixLookup(status="resolved" if cell else "undetermined", cell=cell)
```

- [ ] Implementar reglas de aplicabilidad verificadas con tres estados (sí/no/desconocido), alcance material/personal y motivos citables. Los tests positivos/negativos usarán evidencias revisadas del manual, incluyendo excepciones identificadas; no importar la tabla de producción para generar expectativas de test.
- [ ] Verificar integridad 18 × 18, notas y orientación A/B y probar datos corruptos/requisitos contradictorios. GREEN + controles; commit `feat: add verified convention rules with prerequisite guards`.

## Task 14: Recorrido de siniestros con hechos atribuibles

**Estado de ejecución (1 de septiembre de 2026):** flujo claim cableado a la API. Modelos, invariantes,
puertos y el uso de la aplicabilidad están implementados. El adaptador LangGraph ya
recorre extracción detrás de puerto, recuperación de criterios, aplicación determinista,
explicación y validación; el extractor OpenAI estructurado está aislado del contexto del
manual y probado. El router `POST /api/v1/claims/analyze` está montado por
`bootstrap.build_api()` cuando el puerto `analyze_claim` se compone con éxito;
su DTO omite cualquier `image_path` local. Faltan los cinco casos de desarrollo
auditados y cerrar las reglas/matriz de T13.

**Files:** Crear `backend/src/application/ports/inbound/analyze_claim.py`, `ports/outbound/claim_workflow.py`, `use_cases/analyze_claim_use_case.py`, `services/claim_analysis.py`, `backend/src/infrastructure/adapters/outbound/claim_workflow/langgraph_workflow.py`, `backend/tests/test_claim_workflow.py`. Ampliar modelos claim/decision y el serializador de ejecución de T10.

**Interfaces:** `ClaimInput(text: str, language: Literal["es", "en"], clarifications: tuple[str, ...])`; `ClaimFact(name: str, value: str | None, asserted_by: str | None, source_text: str)`; `ClaimContradiction(fact_name: str, statements: tuple[ClaimFact, ...])`; `ClaimAnalysis(applicability: Literal["applicable", "not_applicable", "undetermined"], convention: Literal["CIDE", "ASCIDE"] | None, decision: Literal["resolved", "conditional", "undetermined", "not_assessed"], party_ids: tuple[str, ...], facts: tuple[ClaimFact, ...], contradictions: tuple[ClaimContradiction, ...], conditions: tuple[str, ...], missing_information: tuple[str, ...], blocks: tuple[AnswerBlock, ...])`. `AnalyzeClaim.execute(claim: ClaimInput) -> Awaitable[ClaimExecution]`; `ClaimExecution(result: ClaimAnalysis, context: tuple[ContextEvidence, ...], trace_id: str | None)`. Los campos de decisión no se guardan como dict libre.

- [x] RED con dos relatos incompatibles de A/B: ambas afirmaciones se conservan con atribución, ninguna se convierte en reconocimiento conjunto. Otro test de guard: una propuesta `conditional` sin condiciones es rechazada.
- [x] Implementar extracción estructurada contra el texto original y nodos `extract_facts`, `retrieve_criteria`, `apply_rules`, `explain`, `validate`. El adaptador OpenAI recibe solo relato/aclaraciones y devuelve hechos atribuidos; los nodos conservan esos hechos, recuperan evidencia y no permiten que una salida generativa sustituya el resultado determinista. Comprobación mínima sobre hechos y conclusión:

```python
if analysis.decision == "conditional" and not analysis.conditions:
    raise InvalidDecisionError("A conditional decision must name its conditions")
if analysis.applicability == "not_applicable" and analysis.decision == "resolved":
    raise InvalidDecisionError("The convention cannot resolve an inapplicable case")
```

`InvalidDecisionError` vive en el módulo de decisiones. La salida del LLM no sobrescribe el resultado determinista. Si el perfil desactiva reglas, la conclusión debe seguir justificada y evaluada contra el manual.
- [ ] Las solicitudes de datos faltantes deben especificar qué resolverían y permitir respuestas condicionadas útiles. No penalizar los cinco ejemplos por no aportar todos los datos administrativos; no inventarlos tampoco. Invocar las mismas etapas de recuperación y evidencia que T8.
- [ ] Ejecutar primero fixtures de integración con dobles y después los cinco casos de desarrollo con rúbricas revisadas; guardar trazas/contexto y analizar todos los errores críticos. GREEN, controles y commit `feat: analyze claim facts and convention outcomes with LangGraph`.

## Task 15: Visión, expansión de contexto y reranking medibles

**Files:** Crear `backend/src/application/services/visual_context.py`, `reranking.py`, `backend/src/application/ports/outbound/reranker.py`, `backend/src/infrastructure/adapters/outbound/reranker/openai_reranker.py`, `backend/tests/test_context_assembly.py`, `backend/configs/hybrid-visual.yaml`. Modificar ambos recorridos para activar componentes por perfil.

**Interfaces:** `Reranker.rank(query: str, candidates: Sequence[Chunk]) -> Awaitable[tuple[str, ...]]` devuelve solo IDs de candidatos. `assemble_context(chunks: Sequence[Chunk], budget: int) -> tuple[ContextEvidence, ...]`; `select_visual_evidence(context: Sequence[ContextEvidence]) -> tuple[PageEvidence, ...]` selecciona únicamente páginas registradas. Un parser/render fallido es error de evidencia, no una imagen inventada.

- [ ] RED: un reranker devuelve un ID inexistente o repetido; el adaptador rechaza el resultado. Otro test asegura que el contexto registrado coincide con lo que se envió tras truncar al presupuesto, no con toda la página fuente.
- [ ] Validar la salida del reranker y no modificar contenido de candidatos:

```python
allowed = {chunk.chunk_id for chunk in candidates}
if len(order) != len(set(order)) or not set(order) <= allowed:
    raise InvalidRankingError("Ranking references invalid candidates")
```

Implementar reranker LLM usando el proveedor ya configurado como candidato inicial, sin exigir otra cuenta. Comparar con `none`, manteniendo límites de candidatos y contexto; no declarar mejoría antes del experimento.
- [ ] Incorporar imágenes originales por Responses API como `input_image`, limitando tamaño/número y conservando versión/región. Incluir cabeceras y notas cuando la interpretación de una celda las requiera. Registrar bytes/hash de artefacto, páginas y coste; los evaluadores visuales reciben las mismas imágenes necesarias.
- [ ] Ejecutar ablaciones de visión/reglas/rerank sobre desarrollo con presupuesto fijo y pruebas de retirada de evidencia/ruido. Guardar fallos y costes; commit `feat: add auditable visual context and optional reranking`.

## Task 16: Automático sin duplicar los recorridos

**Files:** Crear `backend/src/application/ports/inbound/resolve_query.py`, `ports/outbound/query_workflow.py`, `use_cases/resolve_query_use_case.py`, `services/routing.py`, `backend/src/infrastructure/adapters/outbound/query_workflow/langgraph_workflow.py`, `backend/tests/test_query_routing.py`.

**Interfaces:** `RouteDecision(mode: Literal["question", "claim", "clarification_required"], clarification: str | None)`; `ResolveQuery.execute(query: QueryInput) -> Awaitable[QueryExecution | ClaimExecution | RouteDecision]`. El router recibe entrada original, sin etiquetas. Los modos explícitos llaman directamente a sus use cases y no a ResolveQuery.

- [ ] RED con dobles contadores: `question` ejecuta una vez AnswerQuestion y cero AnalyzeClaim; `claim` hace lo contrario; `clarification_required` no ejecuta ninguno. El texto recibido por el flujo debe ser idéntico al input.
- [ ] Implementar nodo clasificador con enum cerrado y aristas condicionales nativas de LangGraph. Despacho conceptual:

```python
match route.mode:
    case "question":
        return await answer_question.execute(query)
    case "claim":
        return await analyze_claim.execute(ClaimInput(query.text, query.language, ()))
    case "clarification_required":
        return route
```

La implementación del grafo conserva esa exclusividad y usa los casos existentes inyectados. Nunca recurre al coordinador desde el recorrido hijo.
- [ ] Versionar prompt/modelo y evaluar definiciones con relato de fondo, escenarios hipotéticos, solicitudes mixtas, falta de datos y ambigüedad de intención. La entrada off-topic debe conservar la política de alcance, no inventar una especialidad nueva. Un error del router se registra como técnico, no como aclaración legítima.
- [ ] Ejecutar la comparación emparejada automático/ explícito con Langfuse, incluyendo coste y calidad final. GREEN + controles; commit `feat: route automatic queries to the existing workflows`.

## Task 17: API de los tres modos, estados y streaming

**Estado de ejecución (1 de septiembre de 2026):** iniciada. Las rutas explícitas de pregunta y de
siniestros están montadas por `bootstrap.build_api()` cuando el puerto
correspondiente se compone con éxito; el router de claims omite cualquier
`image_path` local en su respuesta. La ruta explícita de pregunta
(`POST /api/v1/questions/answer`) traduce únicamente el puerto inbound, conserva
contexto/citas/trace ID y diferencia un fallo técnico (500) de `insufficient_evidence` (200).
La rama automática (T16), el DTO común y el streaming siguen pendientes.

**Files:** Crear `backend/src/infrastructure/adapters/inbound/api/routes/queries.py`, `schemas/query.py`, `streaming.py`, `errors.py`, `backend/tests/test_query_api.py`, `backend/tests/test_streaming_api.py`, `docs/api/openapi.json`. Modificar app y bootstrap.

**Interfaces:** Request común `text`, `language`, `stream`, `profile` opcional permitido; siniestros añade `clarifications`. Response `request_id`, `requested_mode`, `resolved_mode`, `result`, `evidence`, `metadata`. `result.kind` discrimina `question`, `claim`, `clarification`; los estados internos conservan los enums de T8/T14/T16. Error `code`, `message`, `request_id`, `retryable`, sin trazas internas. OpenAPI define JSON y eventos `started`, `stage`, `completed`, `failed`.

- [ ] RED: una consulta con resultado `insufficient_evidence` devuelve 200; un timeout de proveedor devuelve error técnico. Explícito no llama al router. Un perfil no permitido devuelve 422. El resultado claim condicionado conserva conditions.
- [ ] Implementar conversión en infraestructura a esquemas Pydantic discriminados; API solo llama a los puertos de entrada. Para SSE usar soporte FastAPI `EventSourceResponse`/`ServerSentEvent` de la versión fijada, no un protocolo propio. La rama final emite:

```python
yield ServerSentEvent(event="completed", data=response.model_dump(mode="json"))
```

`response` es el mismo DTO que se devuelve sin streaming. Registrar progreso real; no enviar conclusiones provisionales que luego se retiren.
- [ ] Test de generador que falla tras iniciar streaming: emite `failed`; cierre sin terminal es interrupción para el cliente. Comprobar que cancelar no inicia un retry automático ni afirma detener una llamada ya facturada.
- [ ] Exportar OpenAPI y comprobar referencias/payloads de ejemplo sin referencias esperadas del golden. GREEN y commit `feat: expose typed query APIs with bounded progress streaming`.

## Task 18: Frontend independiente y modos de consulta

**Files:** Crear `frontend/package.json`, `pnpm-lock.yaml`, `tsconfig.json`, `vite.config.ts`, `index.html`, `src/main.tsx`, `src/App.tsx`, `src/api/client.ts`, `src/api/generated.ts`, `src/features/assistant/QueryForm.tsx`, `QueryResult.tsx`, `useQuery.ts`, `frontend/tests/query-flow.test.tsx`. Modificar Makefile.

**Interfaces:** Generar DTOs desde `docs/api/openapi.json`; `submitQuery(mode: "auto" | "question" | "claim", input: QueryRequest, signal: AbortSignal) -> Promise<QueryResponse>` para JSON. QueryRequest/QueryResponse son tipos derivados del esquema generado, no modelos mantenidos manualmente. El cliente de streaming usa un parser SSE compatible con POST (por ejemplo `eventsource-parser`, tras comprobar su API), sin `EventSource` GET-only.

- [ ] Crear Vite React/TS y configurar Tailwind/shadcn/ui, Vitest y Testing Library. No generar lógica de responsabilidad ni secretos en frontend. Test RED que muestra la conclusión `conditional` con condiciones visibles y botón «Añadir información»; el test usa un response fixture tipado que no es una etiqueta del manual.
- [ ] Implementar selector visible con Automático inicial y mapa fijo de rutas:

```typescript
const endpoints = {
  auto: "/api/v1/queries/resolve",
  question: "/api/v1/questions/answer",
  claim: "/api/v1/claims/analyze",
} as const;
```

Generar cliente/tipos; conservar texto al cambiar modo. Mostrar modo detectado, errores, progreso y resultado sin porcentajes de confianza ficticios. Deshabilitar envíos duplicados y permitir cancelación.
- [ ] Implementar `useQuery` con estados idle/loading/completed/failed/interrupted; `completed` solo tras evento terminal. Usar `fetch` con AbortSignal y parser existente para POST SSE. No mostrar error de red como abstención del manual. «Añadir información» envía original y aclaraciones del usuario; no concatena análisis del asistente como hechos.
- [ ] `pnpm --dir frontend test --run`, `pnpm --dir frontend build`, comprobación TypeScript y revisión visual de escritorio/pantalla estrecha. Commit `feat: add the three-mode assistant interface`.

## Task 19: Visor PDF y referencias verificables

**Files:** Crear `frontend/src/features/manual/ManualViewer.tsx`, `EvidencePanel.tsx`, `CitationLink.tsx`, `frontend/tests/evidence-panel.test.tsx`, `frontend/e2e/citations.spec.ts`. Modificar QueryResult/App y estilos.

**Interfaces:** `EvidencePanel({ evidenceId, onClose })`; `ManualViewer({ documentUrl, pdfPage, regions })` recibe únicamente URLs registradas y coordenadas verificadas normalizadas respecto a la página visible. Los campos vienen del contrato generado. A falta de región, mostrar «Referencia a la página» sin inventar resaltado.

- [ ] RED: pulsar una cita de PDF página 32 con etiqueta impresa 33 debe abrir 32; el visor no interpreta la etiqueta impresa como índice del documento. Test sin regiones: no dibuja overlay de fragmento.
- [ ] Configurar PDF.js/worker de Vite y navegación a página. Transformación del overlay con la convención ya verificada por T3:

```typescript
const style = {
  left: `${region.x0 * 100}%`,
  top: `${region.y0 * 100}%`,
  width: `${(region.x1 - region.x0) * 100}%`,
  height: `${(region.y1 - region.y0) * 100}%`,
};
```

No habilitar rotación adicional del visor sin transformar también las regiones. Cancelar render anterior al cambiar de página/documento.
- [ ] Verificar manual real: página escaneada, tabla y un fragmento textual con coordenadas contrastadas. Panel al lado en escritorio y superpuesto en estrecho, navegación por teclado y retorno a la respuesta. El control Evaluación enlaza Langfuse; no clona su UI.
- [ ] Ejecutar tests y Playwright sobre abrir/cerrar cita y versión ausente; inspeccionar capturas con el navegador. Commit `feat: show original PDF evidence beside answers`.

## Task 20: Selección de configuración, reserva e informe

**Files:** Crear `backend/src/infrastructure/adapters/outbound/evaluation/experiment_catalog.py`, `backend/configs/experiments.yaml`, `docs/results/development-report.md`, `docs/results/holdout-report.md`, `docs/results/final-profile.json`, `backend/tests/test_experiment_manifest.py`. Modificar CLI de evaluación.

**Interfaces:** `validate_experiment_manifest(manifest: Mapping[str, object]) -> None`; `allianz evaluate --dataset NAME --version VERSION --profile PROFILE --release RELEASE` usa T10 y añade salida de siniestros/router. `allianz evaluate --verify-manifest PATH` verifica fuente, artefactos, dataset, prompts y modelos sin generar respuestas.

- [ ] RED: un hash del dataset distinto del publicado impide ejecutar aunque el nombre coincida. Una repetición usa otro ID de intento; reanudar el mismo intento no aumenta N.
- [ ] Escribir catálogo explícito de experimentos: parser/chunker; densa/BM25/híbrida; rerank; reglas; visión; generador; router. Cambiar una dimensión cada vez, comparar context budget y documentar información adicional. Usar el SDK, sin crear scheduler o runner alternativo. Núcleo de guard:

```python
if loaded_dataset_hash != manifest["dataset_sha256"]:
    raise ValueError("Dataset content differs from the frozen release")
```

- [ ] Ejecutar desarrollo, analizar errores y fijar perfil final antes de reserva. Las rúbricas, métricas principales y umbrales se fijan antes de la comparativa que pretende validarlos. Evaluar reserva una vez con ese perfil, conservar errores y costes; si se usa para corregir, declarar que deja de ser reserva.
- [ ] Exportar resultados por caso y comparativas desde Langfuse, revisar denominadores y presentar incertidumbre por familias. Cero errores críticos observados no significa riesgo cero; no ocultar fallos de juez/publicación. Commit `docs: record reproducible configuration selection and limits` solo después de disponer de resultados reales.

## Task 21: Demo reproducible, documentación y presentación

**Files:** Crear `backend/Dockerfile`, `frontend/Dockerfile`, `docs/operations/demo-runbook.md`, `docs/architecture/implementation-notes.md`, `docs/presentation/allianz-rag.pptx`, `docs/presentation/speaker-notes.md`; modificar Compose, Makefile, README y lista de dependencias bloqueadas. Tests: `backend/tests/integration/test_demo_readiness.py`, `frontend/e2e/demo.spec.ts`.

**Interfaces:** `make setup`, `make services`, `make ingest`, `make evaluate`, `make demo`, `make check` son entradas documentadas. `make demo` no inicia generación del golden ni evaluación pagada; requiere el perfil y artefactos ya preparados. No se publica nada en GitHub automáticamente.

- [ ] Test RED: sin el índice requerido la demo informa no preparada; no muestra una respuesta grabada como resultado vivo. Probar arranque con volumen persistente y una consulta/cita completa.
- [ ] Construir imágenes con lockfiles; puertos en localhost, secretos fuera de imágenes y Git. Smoke operativo:

```bash
docker compose --env-file ops/local.env config --quiet
docker compose --env-file ops/local.env up -d --build
make check
```

Ejecutar en CPU la ruta de contenedores y documentar por separado aceleración nativa. Comprobar reinicio y trazas; no declarar offline el uso de modelos externos.
- [ ] Preparar la presentación con la skill de presentaciones: problema, requisitos, fuente, arquitectura, comparación de candidatos, calidad del golden, resultados, costes, riesgos y demo. Usar datos medidos de T20, no porcentajes ilustrativos. Incluir guion de 30–45 minutos y fallback identificado si falla Internet; no presentarlo como ejecución en directo.
- [ ] Ensayar los cinco casos originales y alguna pregunta documental no memorizada por el router. Revisar accesibilidad, lectura de citas y errores. Documentar qué hace cada comando, cómo aportar el manual con hash esperado y dónde configurar claves sin enviarlas al chat.
- [ ] Revisión final de código y artefactos, controles completos, inspección visual de slides y demo. Commit `chore: package the verified local demo and interview materials`. Mantener Git local hasta que el usuario pida crear remoto o subirlo.

## Cobertura y puertas de salida

| Especificación | Tareas |
| --- | --- |
| Fuente, alcance y trazabilidad | T1–T3, T12, T21. |
| Carpetas, puertos, stack y aislamiento de frameworks | T1, T4, T8, T14, T16–T18. |
| Ingesta, chunking y recuperación intercambiables | T2–T4, T7, T15, T20. |
| Reglas, visión, incertidumbre y hechos atribuidos | T12–T15. |
| Automático y modos explícitos | T16–T18, T20. |
| API, errores, SSE y citas | T6, T8, T17–T19. |
| Golden set y referencia independiente | T9, T12–T13. |
| Langfuse/Ragas, jueces, métricas y reproducibilidad | T5, T9–T12, T20. |
| Operación local, seguridad y entrega | T1, T5–T6, T17, T21. |

No marcar una tarea como completa por tener sus archivos: comprobar su salida. Una integración omitida por falta de Docker/clave figura como no ejecutada. Ningún fallback debe presentar métricas simuladas como resultados del manual. Las tareas de datos y revisión pueden requerir varias sesiones; se reanudan por item publicado, sin atajos de calidad.

## Referencias para comprobar APIs al ejecutar

- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).
- [Langfuse Experiment SDK](https://langfuse.com/docs/evaluation/experiments/experiments-via-sdk).
- [Langfuse datasets y versiones](https://langfuse.com/docs/evaluation/experiments/datasets).
- [Ragas FactualCorrectness](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/factual_correctness/).
- [Ragas Testset Generation](https://docs.ragas.io/en/stable/getstarted/rag_testset_generation/).
- Las fuentes de extracción, Qdrant, LangGraph, frontend y self-hosting están enlazadas en los anexos de la especificación.

## Registro de ejecución

Al comenzar cada tarea registrar rama, commit inicial, comandos y resultados. Marcar checkboxes solo después de ejecutar las acciones. El plan puede ajustarse por una incompatibilidad probada, conservando la decisión y sin cambiar silenciosamente un requisito aprobado.
