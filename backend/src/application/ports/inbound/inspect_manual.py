"""Inbound port for manual inspection."""

from pathlib import Path
from typing import Protocol

from domain.models.document import DocumentManifest


class InspectManual(Protocol):
    """Inspect a source manual and optionally verify its expected hash."""

    def execute(self, source: Path, expected_sha256: str | None = None) -> DocumentManifest:
        """Return the verified manifest for a source document."""
        ...
