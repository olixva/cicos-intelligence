"""Application execution values for source-grounded convention analysis."""

from dataclasses import dataclass

from application.models.query import ContextEvidence
from domain.models.decision import ClaimAnalysis


@dataclass(frozen=True, slots=True)
class ClaimExecution:
    """A claim result and the exact document evidence supplied to the workflow."""

    result: ClaimAnalysis
    context: tuple[ContextEvidence, ...]
    trace_id: str | None = None
