"""Minimal outbound port for resolving immutable page evidence."""

from typing import Protocol

from domain.models.evidence import PageEvidence


class EvidenceReader(Protocol):
    """Resolve a registered page without exposing publication operations."""

    def get(self, evidence_id: str) -> PageEvidence: ...
