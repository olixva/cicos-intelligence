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
