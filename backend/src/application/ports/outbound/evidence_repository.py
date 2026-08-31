"""Outbound port for immutable page evidence storage."""

from pathlib import Path
from typing import Protocol

from domain.models.evidence import Extraction, PageEvidence


class EvidenceRepository(Protocol):
    """Publish and retrieve evidence for one explicit parser version."""

    def publish(self, extraction: Extraction) -> Path:
        """Atomically publish a validated extraction and return its directory."""
        ...

    def get(self, evidence_id: str) -> PageEvidence:
        """Return one page evidence record by its validated identifier."""
        ...
