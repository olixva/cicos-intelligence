"""Outbound port for extracting immutable document evidence."""

from pathlib import Path
from typing import Protocol

from domain.models.evidence import Extraction


class DocumentParser(Protocol):
    """Parse a source document into page-level evidence."""

    def parse(self, source: Path) -> Extraction:
        """Return evidence derived from one immutable read of ``source``."""
        ...
