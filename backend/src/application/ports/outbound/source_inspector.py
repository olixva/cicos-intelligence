"""Outbound port for low-level source document inspection."""

from pathlib import Path
from typing import Protocol

from domain.models.document import DocumentManifest


class SourceInspector(Protocol):
    """Read and describe a source document."""

    def inspect(self, source: Path) -> DocumentManifest:
        """Return the manifest derived from the source document."""
        ...
