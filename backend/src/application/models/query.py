"""Immutable values for grounded document questions and their execution evidence."""

from dataclasses import dataclass
from typing import Literal

from domain.models.evidence import PageEvidence

type AnswerStatus = Literal["answered", "partial", "insufficient_evidence", "out_of_scope"]
type EvidenceDelivery = Literal["text", "image", "rule"]


@dataclass(frozen=True, slots=True)
class QueryInput:
    """One validated user question, independent from transport concerns."""

    text: str
    language: Literal["es", "en"] = "es"

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("query text must be nonempty")
        if self.language not in ("es", "en"):
            raise ValueError("query language must be es or en")


@dataclass(frozen=True, slots=True)
class AnswerBlock:
    """A response passage and the source identifiers claimed for that passage."""

    text: str
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("answer block text must be nonempty")
        if any(not evidence_id.strip() for evidence_id in self.evidence_ids):
            raise ValueError("answer block evidence identifiers must be nonempty")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("answer block evidence identifiers must be unique")


@dataclass(frozen=True, slots=True)
class QuestionAnswer:
    """A closed document-answer result before or after grounding validation."""

    status: AnswerStatus
    blocks: tuple[AnswerBlock, ...]

    def __post_init__(self) -> None:
        if self.status not in (
            "answered",
            "partial",
            "insufficient_evidence",
            "out_of_scope",
        ):
            raise ValueError("unsupported answer status")


@dataclass(frozen=True, slots=True)
class ContextEvidence:
    """The exact payload delivered to the model, linked to immutable source evidence."""

    evidence_id: str
    text: str
    source: PageEvidence
    delivery: EvidenceDelivery = "text"

    def __post_init__(self) -> None:
        if not self.evidence_id.strip() or not self.text.strip():
            raise ValueError("context evidence identifier and text must be nonempty")
        if self.evidence_id != self.source.evidence_id:
            raise ValueError("context evidence must match its source identifier")
        if self.delivery not in ("text", "image", "rule"):
            raise ValueError("unsupported evidence delivery")


@dataclass(frozen=True, slots=True)
class QueryExecution:
    """The result plus the exact evidence available during its generation."""

    result: QuestionAnswer
    context: tuple[ContextEvidence, ...]
    trace_id: str | None = None
