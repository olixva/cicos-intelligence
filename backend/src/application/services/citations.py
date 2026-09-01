"""Application services that resolve source-based citation identifiers."""

from collections.abc import Sequence

from application.ports.outbound.evidence_repository import EvidenceRepository
from domain.models.evidence import PageEvidence


def resolve_citations(
    ids: Sequence[str], repository: EvidenceRepository
) -> tuple[PageEvidence, ...]:
    """Resolve citations in caller order through the evidence repository boundary."""

    return tuple(repository.get(evidence_id) for evidence_id in ids)
