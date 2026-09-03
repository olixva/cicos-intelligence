# Ingesta y recuperación

Cómo se convierte el PDF del manual en evidencia citable y en un índice
consultable, y cómo se recupera después.

## La fuente

| | |
|---|---|
| Fichero | `data/raw/Manual-cide-ascide-y-cicos.pdf` |
| SHA-256 | `b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344` |
| Páginas | 111 |
| Edición | noviembre de 2004 |

El hash es parte de la identidad de todo lo que se deriva del manual:
publicaciones de evidencia, artefactos de reglas, firmas de índice y
`evidence_id`. Un documento distinto produce identificadores distintos y no
puede colarse en un índice existente.

La ingesta por API sólo acepta este documento verificado.

## Verificación previa

```bash
uv run --project backend allianz inspect-manual \
  data/raw/Manual-cide-ascide-y-cicos.pdf \
  --expected-sha256 b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344
```

Devuelve JSON con el SHA-256, el nombre y el número de páginas. Lee la fuente
sin escribir en ella: comprueba identidad y legibilidad, nada más.

## Los dos parsers

Ambos publican bajo el mismo contrato y ambos están publicados para el
documento verificado. **La publicación de `pypdf` viaja versionada en el
repositorio** (`data/extractions/<sha256>/pypdf-6.16.2/`, 488 KB), junto al
manual original: sin ella, un checkout limpio no puede validar la evidencia
que citan los artefactos firmados. La de Docling, de 20 MB, se regenera con el
comando de abajo.

### `pypdf` — línea base

```bash
uv run --project backend --group ingestion --extra local-rag allianz ingest \
  data/raw/Manual-cide-ascide-y-cicos.pdf --parser pypdf --output data/extractions
```

Texto plano por página, sin dependencias pesadas ni red. Identidad del parser:
`pypdf-6.16.2`. Es el parser del perfil `baseline` y el que sirve hoy la
demostración.

### `docling` — estructurado

Requiere preparar antes el bundle local de modelos. Es el **único** paso de
ingesta que usa red:

```bash
uv run --project backend --group ingestion allianz prepare-ingestion-models \
  --output "$HOME/.cache/allianz-rag/docling-artifacts-v1"

uv run --project backend --group ingestion allianz ingest \
  data/raw/Manual-cide-ascide-y-cicos.pdf --parser docling --output data/extractions
```

`prepare-ingestion-models` descarga nueve ficheros (layout, tablas y RapidOCR)
desde revisiones exactas de HuggingFace y ModelScope, verifica los SHA-256
fijados en `model_artifacts.py` y publica un bundle local de ~409 MB de forma
atómica. La ingesta normal valida ese bundle y **nunca descarga modelos de
forma implícita**. La ruta por defecto se puede cambiar con
`ALLIANZ_DOCLING_ARTIFACTS`.

La identidad del parser incluye el digest efectivo del bundle:

```
docling-2.124.0-pdfium-5.13.0-rapidocr-latin-torch-r2-3d1d1af9689b76cf
```

Esta publicación retiene elementos con su tipo (`section_header`, `text`,
`table`, `footnote`…), *bounding boxes* por elemento, el JSON crudo de Docling,
Markdown, diagnósticos, el PDF original y un PNG independiente a 144 dpi por
cada página física. Las regiones son lo que permite resaltar en el visor la
zona exacta de la página que sostiene una cita.

La comparación entre ambos parsers está disponible como comando:

```bash
uv run --project backend --group ingestion allianz compare-parsers SOURCE --output DIR
```

## Contrato de publicación

Una publicación es inmutable y vive en una ruta que declara su procedencia:

```
data/extractions/<sha256 del documento>/<parser-versión>/
├── publication.json   raíz que liga todos los ficheros por SHA-256
├── manifest.json      identidad del documento y número de páginas
├── pages.jsonl        una línea por página física
├── original.pdf       el PDF exacto que se leyó
└── (docling) document.json, document.md, extraction.json,
             configuration.json, diagnostics.json, pages/*.png
```

Reglas del contrato:

- **Una sola lectura de la fuente.** El hash del manifiesto y las páginas
  extraídas salen de los mismos bytes.
- **Escritura atómica.** Se escribe una publicación temporal completa y se
  renombra al directorio definitivo. No existe un estado intermedio legible.
- **Todas las páginas físicas se preservan**, incluidas las que están en
  blanco, para que la numeración de `pdf_page` nunca se desplace.
- **`publication.json` se verifica antes de leer evidencia.** Si un fichero no
  cuadra con su hash, la publicación no se usa.
- La salida estándar de la CLI imprime hashes y tamaños, nunca contenido
  binario.

Cada página produce un `evidence_id` estable:

```
sha256:b9c70c74…c8344:page:9
```

## Chunking

El chunking es determinista y conserva la identidad de página de cada
fragmento (`application/services/chunking.py`):

- **`fixed`** (perfil `baseline`): ventanas de 1200 caracteres con 200 de
  solape sobre el flujo de texto exacto de las páginas. Cada fragmento arrastra
  los `evidence_id` de todas las páginas que toca.
- **`sections`** (perfil `structured`): agrupa por sección respetando la
  jerarquía de encabezados de Docling, con un máximo de 1200 caracteres. Las
  tablas y los bloques de observaciones son **atómicos**: no se parten, porque
  media tabla de culpabilidad no es evidencia de nada.

## Perfiles

Los perfiles viven en `backend/configs/` y son el catálogo cerrado que el API
acepta en el campo `profile`.

| | `baseline` | `structured` |
|---|---|---|
| Parser | pypdf | docling |
| Chunker | `fixed` (1200 / 200) | `sections` (máx. 1200) |
| Embeddings | `text-embedding-3-small`, 1536 dim | igual |
| BM25 | español | español |

Estado medido en el entorno local: `baseline` publica 118 fragmentos y es el
índice **activo** bajo el alias `allianz-manual-active`; `structured` publica
109 fragmentos y está publicado como colección alternativa. La promoción de un
perfil a activo se decide por evaluación comparada, no por disponibilidad: que
una técnica exista no demuestra que mejore los resultados.

## Índices en Qdrant

```bash
make index-baseline    # el atajo para el perfil baseline y el manual verificado

uv run --project backend --extra local-rag allianz index \
  --document-hash <sha256> --parser pypdf \
  --evidence-root data/extractions --profile baseline
```

Cada publicación de índice crea una colección nueva con nombre derivado de su
firma y mueve después el alias `allianz-manual-active`. La firma
(`IndexSignature`) reúne trece campos:

`document_hash`, `parser`, `chunker`, `embedding_model`, `dimensions`,
`lexical_language`, `retrieval_mode`, `fusion`, `reranker`, `vision`,
`ruleset`, `generator` y `prompt_versions`.

Consultar un índice cuya firma no coincide con la que espera el runtime es un
error explícito, no una degradación silenciosa. Las operaciones de gestión son
comandos propios:

```bash
allianz list-index-versions            # colecciones publicadas y su firma
allianz index-rollback --collection C  # verifica la firma antes de mover el alias
```

## Recuperación

La consulta es híbrida y se ejecuta dentro de Qdrant:

- **Densa**: embeddings de OpenAI (`text-embedding-3-small`, 1536 dimensiones).
- **Léxica**: BM25 español vía FastEmbed, con una particularidad deliberada —
  se retiran de la lista de *stopwords* los tokens de negación (`no`, `ni`,
  `sin`, `nunca`, `jamás`, `ningún`…). En un manual de convenios, «no aplica»
  y «aplica» no pueden colapsar al mismo término.
- **Fusión**: RRF nativo de Qdrant.

El modo de recuperación (`dense`, `sparse`, `hybrid`) es configuración, no
código: los tres caminos son intercambiables por perfil.
