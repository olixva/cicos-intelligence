# Allianz RAG backend

The backend provides a local command that verifies a source PDF's SHA-256 and
basic PDF readability without changing the source file.

Structured local ingestion is available through the locked `ingestion` dependency group:

```bash
uv run --project backend --group ingestion allianz prepare-ingestion-models \
  --output "$HOME/.cache/allianz-rag/docling-artifacts-v1"

uv run --project backend --group ingestion allianz ingest SOURCE \
  --parser docling --output data/extractions
```

Model preparation is explicit and networked; normal ingestion is offline. The local bundle pins
and verifies the effective layout, table, and RapidOCR files and contributes its digest to the
parser identity. The default path is shown above and can be overridden with
`ALLIANZ_DOCLING_ARTIFACTS`.

The command writes the original PDF, independent 144 dpi page renders, raw Docling JSON,
Markdown, layout elements, and diagnostics to an immutable parser-versioned directory. Standard
output contains hashes and sizes only; source and rendered bytes remain in the publication. A
`publication.json` root binds every metadata and binary file by SHA-256 before evidence is read.
