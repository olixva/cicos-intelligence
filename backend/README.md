# Allianz RAG backend

The backend provides a local command that verifies a source PDF's SHA-256 and
basic PDF readability without changing the source file.

Structured local ingestion is available through the locked `ingestion` dependency group:

```bash
uv run --project backend --group ingestion allianz ingest SOURCE \
  --parser docling --output data/extractions
```

The command writes the original PDF, independent 144 dpi page renders, raw Docling JSON,
Markdown, layout elements, and diagnostics to an immutable parser-versioned directory. Standard
output contains hashes and sizes only; source and rendered bytes remain in the publication.
