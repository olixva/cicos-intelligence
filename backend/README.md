# Backend

FastAPI + LangGraph sobre una arquitectura hexagonal. Expone el API que
consume la SPA y la CLI `allianz` que opera la ingesta, los índices, las
reglas y el golden set.

Contexto general en el [README raíz](../README.md); arquitectura completa en
[docs/arquitectura.md](../docs/arquitectura.md).

## Estructura

```
backend/
├── src/
│   ├── domain/            reglas y modelos de negocio, sin dependencias externas
│   │   ├── models/        ClaimInput, ClaimAnalysis, RuleEvaluation, PageEvidence…
│   │   └── rules/         aplicabilidad, motor de ruleset, tabla CIDE,
│   │                      validación de artefactos firmados
│   ├── application/
│   │   ├── ports/         puertos de entrada y salida (Protocol)
│   │   ├── services/      lógica pura: chunking, citas, guardarraíles, routing
│   │   └── use_cases/     implementación de los puertos de entrada
│   ├── infrastructure/
│   │   ├── adapters/inbound/   API FastAPI y CLI
│   │   ├── adapters/outbound/  Qdrant, OpenAI, Docling, pypdf, Langfuse,
│   │   │                       repositorio de evidencia en ficheros
│   │   └── config/        perfiles y carga de artefactos de reglas
│   ├── bootstrap.py       raíz de composición
│   └── asgi_local.py      factoría ASGI para uvicorn
├── configs/               perfiles `baseline` y `structured`
├── scripts/               herramientas independientes (runner de evaluación,
│                          comparación de parsers, export/chequeo de OpenAPI,
│                          aprovisionamiento de prompts, transcripción de la matriz)
└── tests/                 505 tests en 18 módulos, agrupados por área
```

Las dependencias apuntan siempre hacia dentro: el dominio no importa nada de
infraestructura, y toda dependencia externa entra por un puerto que en los
tests se sustituye por un doble. **La suite completa corre sin OpenAI, sin
Qdrant y sin Langfuse.**

## Instalación

El proyecto se gestiona con [uv](https://docs.astral.sh/uv/) y requiere Python
3.14. Los extras están separados para que la inspección de la fuente no
arrastre el stack completo:

| Grupo / extra | Qué añade |
|---|---|
| (base) | FastAPI, Pydantic, pypdf, uvicorn, sse-starlette |
| `--extra local-rag` | Qdrant, OpenAI, LangGraph, Langfuse, FastEmbed |
| `--group ingestion` | Docling y pypdfium2 |
| `--group dev` | pytest, ruff, pyright |

```bash
uv sync --project backend --extra local-rag --group ingestion --group dev
```

## Servir

```bash
make serve-backend    # aprovisiona prompts y arranca uvicorn en 127.0.0.1:8000
```

El objetivo carga `.env`, mapea las claves de Langfuse desde `ops/local.env` y
crea de forma idempotente los prompts numerados que el API espera. Swagger en
<http://127.0.0.1:8000/docs>; el contrato está documentado en
[docs/api.md](../docs/api.md).

## CLI `allianz`

```bash
uv run --project backend allianz <subcomando>
```

| Subcomando | Para qué |
|---|---|
| `inspect-manual` | verifica SHA-256 y legibilidad del PDF sin escribir en él |
| `ingest` | publica evidencia con `--parser pypdf` o `--parser docling` |
| `prepare-ingestion-models` | descarga y verifica el bundle local de Docling |
| `compare-parsers` | compara dos publicaciones del mismo documento |
| `index` | construye y publica un índice en Qdrant, y mueve el alias |
| `list-index-versions` | lista las colecciones publicadas y su firma |
| `index-rollback` | verifica la firma antes de devolver el alias |
| `answer` | resuelve una consulta documental desde la línea de comandos |
| `rules validate` | valida matriz y ruleset: esquema, firma, hash y evidencia |
| `rules compare-transcriptions` | diferencias entre dos transcripciones de la matriz |
| `golden validate / freeze / publish` | valida, congela y publica el golden set |
| `doctor` | comprobaciones acotadas de servicios y credenciales |

## Verificación

```bash
make check-backend    # ruff + formato + pyright estricto + pytest
make test-backend     # sólo los tests
```

Pyright corre en modo estricto sobre `src/` y está en cero. Los 505 tests
están agrupados por área:

| Fichero | Área |
|---|---|
| `test_rules_engine.py`, `test_rules_artifacts.py` | dominio de reglas y artefactos firmados |
| `test_claim_workflow.py`, `test_claim_analysis.py` | grafo de siniestros y su servicio |
| `test_question_workflow.py`, `test_routing.py` | grafo documental y enrutado |
| `test_api_envelope.py`, `test_api_routes.py` | contrato HTTP y rutas |
| `test_ingestion.py`, `test_document_parsers.py` | ingesta y adaptadores de parseo |
| `test_chunking_profiles.py`, `test_build_retrieval_index.py` | chunking, perfiles e índices |
| `test_openai_adapters.py`, `test_langfuse.py` | adaptadores de proveedor |
| `test_evaluation.py`, `test_golden_cli.py` | evaluación y golden set |
| `test_cli.py`, `test_input_guardrails.py` | CLI y guardarraíles |
| `tests/integration/` | contratos contra Qdrant y Docling reales |

## Contrato OpenAPI

```bash
uv run --project backend python backend/scripts/export_openapi.py   # regenerar
make check-openapi                                                  # detectar drift
```

`docs/api/openapi.json` es la fuente desde la que el frontend genera sus
tipos. `check-openapi` compara el esquema que produce el código con el fichero
publicado y, del lado del cliente, regenera los tipos y falla si difieren.
