"""Closed-enum routing decisions and execution wrappers for auto-dispatch."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from application.models.claim import ClaimExecution
from application.models.query import QueryExecution, QueryInput

type RouteDecision = Literal["question", "claim", "clarification_required"]


@dataclass(frozen=True, slots=True)
class RouteClassification:
    """Closed enum decision plus the rationale the classifier surfaced."""

    decision: RouteDecision
    rationale: str | None = None


@dataclass(frozen=True, slots=True)
class ClarificationResult:
    """A bounded clarification message with the empty fields it expects."""

    message: str
    missing_fields: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RouteExecution:
    """The dispatched flow result and the classification that selected it."""

    query: QueryInput
    classification: RouteClassification
    dispatch: QueryExecution | ClaimExecution | ClarificationResult = field()
    trace_id: str | None = None
