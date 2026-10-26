# CICOS Intelligence

Sistema RAG local sobre el **Manual de convenios CIDE / ASCIDE / CICOS**
(edición de noviembre de 2004, 111 páginas). Responde preguntas del manual
citando las páginas que las sostienen, y analiza relatos de siniestro
aplicando un conjunto de reglas firmadas derivadas de esa misma fuente.

La propiedad que gobierna todo el diseño: **cuando no hay evidencia para
decidir, el sistema dice qué falta en lugar de inventar una conclusión**.

---

## Qué hace

**Consulta documental.** Recuperación híbrida (densa + BM25 español, fusión
RRF) sobre el manual, generación con citas obligatorias y una validación
determinista posterior que recorta cualquier cita que el modelo no pueda
sostener. La respuesta puede ser completa, parcial, sin evidencia suficiente o
fuera de alcance.

**Análisis de siniestros.** El modelo extrae hechos tipados del relato; la
decisión la toman reglas deterministas: la puerta de aplicabilidad del
Convenio, un ruleset de 14 reglas firmadas y la tabla de culpabilidad CIDE de
18×18 transcrita por dos vías automatizadas y con revisión firmada por el autor.
La matriz aún necesita revisión experta antes de cualquier uso operativo. Si
falta un dato decisorio, el flujo se detiene y pregunta exactamente por él.

**Enrutado automático.** Jev decide con una salida tipada entre consulta,
siniestro o petición de aclaración; el router OpenAI Luna queda como opción de
comparación.

**Trazabilidad.** Cada cita es un `evidence_id` que abre el PDF original en la
página exacta. Cada regla evaluada informa de sus entradas y su resultado;
cuando hay evidencia, incluye sus `evidence_id` y las páginas del PDF. Las
consultas, las rutas `auto` y los análisis de siniestro incluyen el identificador
y el enlace de Langfuse cuando el servicio está configurado. Si `claim` se
interrumpe para pedir datos, también conserva el `thread_id` para reanudarlo.

## Cómo está montado

```
prueba-allianz/
├── backend/     FastAPI + LangGraph, arquitectura hexagonal   → backend/README.md
├── frontend/    SPA React 19 + Vite                           → frontend/README.md
├── data/
│   ├── raw/         el manual original
│   ├── extractions/ publicación baseline de evidencia (pypdf), versionada
│   ├── rules/       artefactos firmados (ruleset, matriz CIDE, catálogo D.A.A.)
│   └── evaluation/  golden set y sus releases congeladas
├── docs/        documentación del sistema                     → docs/README.md
├── ops/         configuración de los servicios locales
├── compose.yaml Qdrant + Langfuse (Postgres, ClickHouse, Redis, MinIO)
└── Makefile     puesta en marcha y verificación
```

## Puesta en marcha

```bash
# 1. Credenciales
cp .env.example .env               # clave de OpenAI, modelos, Langfuse
cp ops/local.env.example ops/local.env

# 2. Servicios locales (Qdrant + Langfuse)
make local-services-up

# 3. Verificar la fuente y publicar el índice en Qdrant
make verify-source     # comprueba el SHA-256 y la legibilidad del manual
make index-baseline    # publica el índice y mueve el alias activo

# 4. Arrancar
make serve-backend     # http://127.0.0.1:8000
make serve-frontend    # http://127.0.0.1:5173
```

No hay que reingerir el manual: su publicación baseline viene en el
repositorio. `make doctor` comprueba que los servicios, el alias del índice y
las credenciales están en su sitio. El detalle completo, incluida la ingesta
estructurada con Docling, está en [docs/operacion.md](docs/operacion.md).

## Verificación

```bash
make check-all       # backend + frontend + contratos OpenAPI
```

| Gate | Qué cubre |
|---|---|
| `make check-backend` | ruff, formato, pyright estricto y 602 tests (601 aprobados, 1 omitido) |
| `make check-frontend` | eslint, tsc, 99 tests de Vitest y build de producción |
| `make check-openapi` | que el contrato publicado y los tipos del cliente no hayan derivado |
| `make test-e2e` | Playwright contra la aplicación real |

## Documentación

| | |
|---|---|
| [docs/arquitectura.md](docs/arquitectura.md) | Capas, flujos y decisiones de diseño |
| [docs/ingesta-y-recuperacion.md](docs/ingesta-y-recuperacion.md) | Del PDF al índice consultable |
| [docs/reglas-y-decision.md](docs/reglas-y-decision.md) | Reglas firmadas, tabla CIDE y entrevista |
| [docs/api.md](docs/api.md) | Contrato HTTP |
| [docs/evaluacion.md](docs/evaluacion.md) | Golden set, métricas y resultados |
| [docs/operacion.md](docs/operacion.md) | Servicios, variables y comandos |
| [docs/entrega/README.md](docs/entrega/README.md) | Índice de entrega y trazabilidad con el enunciado |
| [docs/entrega/memoria.md](docs/entrega/memoria.md) | Memoria técnica del TFM |
| [docs/entrega/validacion.md](docs/entrega/validacion.md) | Resultados de validación y límites actuales |
| [docs/entrega/presentacion.pptx](docs/entrega/presentacion.pptx) | Presentación de defensa |
| [backend/README.md](backend/README.md) | Backend en detalle |
| [frontend/README.md](frontend/README.md) | Frontend en detalle |

## Alcance de la fuente

- **El manual es la edición de noviembre de 2004.** Es la fuente evaluada; no
  es derecho vigente ni una decisión operativa de Allianz.
- **El manual no define qué maniobra representa cada casilla `A0`–`A17`.** Son
  casillas del apartado 12 del parte amistoso europeo, un formulario externo al
  manual; el catálogo que las traduce declara esa procedencia y no cita el
  manual como fuente.
- **El alcance del Convenio no es responsabilidad civil general.** El sistema
  evalúa aplicabilidad y criterios convencionales; no emite una opinión general
  de responsabilidad.
- **La matriz CIDE 18×18 se transcribió por dos vías automatizadas y el autor
  firmó la revisión del artefacto.** No hubo diferencias entre las vías; eso no
  equivale a una validación por una persona experta del dominio. Véase
  [reglas y decisión](docs/reglas-y-decision.md).
