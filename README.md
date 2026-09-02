# Allianz local RAG

This repository starts with a reproducible inspection of the supplied source manual.

```bash
uv run --project backend allianz inspect-manual \
  /Users/aoc/Downloads/Manual-cide-ascide-y-cicos.pdf \
  --expected-sha256 b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344
```

The command returns JSON with the SHA-256, filename, and PDF page count. It reads the
source without writing to it. This verifies the source identity and that it is readable;
it does not extract tables or provide RAG answers.

## Baseline ingestion

```bash
uv run --project backend allianz ingest \
  /Users/aoc/Downloads/Manual-cide-ascide-y-cicos.pdf \
  --parser pypdf \
  --output data/extractions
```

The composition root maps `pypdf` to `PypdfDocumentParser` and constructs its
`FilesystemEvidenceRepository` with that parser's exact version (currently
`pypdf-6.16.2`). It reads each source once, so the manifest hash and extracted pages
come from the same bytes. The repository writes a complete temporary publication and
renames it to `data/extractions/{sha256}/{parser-version}/`; retrieval is bound to that
explicit parser version. The resulting `manifest.json` and `pages.jsonl` preserve every
physical PDF page, including blank pages. See [the baseline review](docs/ingestion-baseline.md)
for known extraction losses.

## Structured ingestion

```bash
uv run --project backend --group ingestion allianz prepare-ingestion-models \
  --output "$HOME/.cache/allianz-rag/docling-artifacts-v1"

uv run --project backend --group ingestion allianz ingest \
  /Users/aoc/Downloads/Manual-cide-ascide-y-cicos.pdf \
  --parser docling \
  --output data/extractions
```

The preparation command is the only ingestion path that uses the network. It downloads nine files
from exact upstream revisions, verifies their pinned SHA-256 values, and publishes a 390 MB local
bundle atomically. Normal ingestion validates that bundle and never downloads models implicitly.
Set `ALLIANZ_DOCLING_ARTIFACTS` only when using a different local path.

This explicit mode retains source-based elements, raw Docling JSON and Markdown, diagnostics, the
exact original PDF, and an independent 144 dpi PNG for every physical page. The parser identity
includes the effective model-bundle digest. The CLI prints asset hashes and sizes rather than
binary content. A complete run over the supplied 111-page manual measured about 3.40 GiB peak RSS
on the reviewed macOS environment. See the
[parser comparison](docs/ingestion/parser-comparison.md) for the page 32 OCR limitation and the
unverified page 101 matrix extraction.

Run the backend quality checks with:

```bash
make check-backend
```

## Local operations

### Bootstrap (one-time)

```bash
# 1. Bring up the local services (Qdrant, Langfuse, postgres, redis, clickhouse, minio)
make local-services-config   # validate compose.yaml against ops/local.env
make local-services-up       # docker compose up -d

# 2. Inspect the source PDF
uv run --project backend allianz inspect-manual \
  /Users/aoc/Downloads/Manual-cide-ascide-y-cicos.pdf \
  --expected-sha256 b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344

# 3. Ingest with pypdf (baseline) and publish
uv run --project backend --group ingestion --extra local-rag allianz ingest \
  /Users/aoc/Downloads/Manual-cide-ascide-y-cicos.pdf \
  --parser pypdf \
  --output data/extractions

# 4. (Optional) Ingest with docling for structured extraction + original.pdf
uv run --project backend --group ingestion allianz prepare-ingestion-models \
  --output "$HOME/.cache/allianz-rag/docling-artifacts-v1"
uv run --project backend --group ingestion allianz ingest \
  /Users/aoc/Downloads/Manual-cide-ascide-y-cicos.pdf \
  --parser docling \
  --output data/extractions

# 5. Index into Qdrant (alias `allianz-manual-active`)
# (handled by build_api() at startup — see `make serve-backend`)

# 6. Run backend checks
make check-backend
```

### Daily

```bash
make local-services-up                # if not running
make serve-backend                    # backend on :8000
pnpm --dir frontend dev              # frontend on :5173 (vite HMR)

# Visit
open http://127.0.0.1:5173/          # chat UI
open http://127.0.0.1:8000/docs       # FastAPI Swagger
open http://127.0.0.1:3000/           # Langfuse UI (login: see ops/local.env)
open http://127.0.0.1:6333/dashboard  # Qdrant dashboard
```

### Docker (alternative to local venv)

```bash
docker build -t allianz-backend -f backend/Dockerfile .
docker build -t allianz-frontend -f frontend/Dockerfile .
docker run --rm -p 8000:8000 --env-file ops/local.env allianz-backend
docker run --rm -p 5173:5173 allianz-frontend
```

### Doctor

```bash
make doctor   # allianz doctor — checks Qdrant alias, Langfuse env, etc.
```

## Limitations

- **Manual catalog requires `original.pdf` in the publication directory** (post-fix commit `0cd56ed`). The pypdf baseline does not persist the source PDF by design; copy or symlink the original into `data/extractions/{sha256}/pypdf-6.16.2/original.pdf` before starting the backend, or re-ingest with `--parser docling` to get it automatically.
- **PDF catalog 404 on first start**: the `data/extractions/{sha256}/pypdf-6.16.2/` directory must exist with `manifest.json`, `pages.jsonl`, AND `original.pdf`. See bootstrap step 3.
- **The 2004 manual is the source scope**; do not state it is current law.
