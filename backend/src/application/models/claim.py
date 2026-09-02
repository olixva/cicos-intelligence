"""Application execution values for source-grounded convention analysis."""

from dataclasses import dataclass

from application.models.query import ContextEvidence
from domain.models.claim import ClaimFact
from domain.models.decision import ClaimAnalysis


@dataclass(frozen=True, slots=True)
class ExtractedClaimFacts:
    """Structured, attributed observations extracted from the user narrative only."""

    party_ids: tuple[str, ...]
    facts: tuple[ClaimFact, ...]

    def __post_init__(self) -> None:
        if len(set(self.party_ids)) != len(self.party_ids) or any(
            not party_id.strip() for party_id in self.party_ids
        ):
            raise ValueError("claim party identifiers must be nonempty and unique")


@dataclass(frozen=True, slots=True)
class ClaimExecution:
    """A claim result and the exact document evidence supplied to the workflow."""

    result: ClaimAnalysis
    context: tuple[ContextEvidence, ...]
    trace_id: str | None = None
    trace_url: str | None = None
