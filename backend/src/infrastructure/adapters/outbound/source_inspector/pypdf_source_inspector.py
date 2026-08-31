"""pypdf-backed implementation of source document inspection."""

from pathlib import Path

from domain.models.document import DocumentManifest
from infrastructure.adapters.outbound.pdf_source import open_pdf_source


class PypdfSourceInspector:
    """Inspect one readable, unencrypted PDF without modifying it."""

    def inspect(self, source: Path) -> DocumentManifest:
        """Read document bytes once and derive a minimal manifest from them."""
        return open_pdf_source(source).manifest
