"""Inbound port for baseline document ingestion."""

from pathlib import Path
from typing import Protocol

from domain.models.evidence import Extraction


class IngestDocument(Protocol):
    """Extract and publish every physical page from a source document."""

    def execute(self, source: Path) -> Extraction:
        """Publish source evidence and return the extraction that was recorded."""
        ...
