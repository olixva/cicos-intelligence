"""HTTP representations for the closed-enum auto router endpoint.

The DTO intentionally mirrors the closed ``RouteDecision`` enum plus the
selected dispatch result. No local asset path is ever exposed; the
clarification branch emits a message and an empty ``missing_fields``
tuple, so the frontend can ask follow-up questions without leaking the
classifier rationale verbatim.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from domain.models.routing import RouteExecution


class _ResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class QueryResolveRequest(_ResponseModel):
    """One user query for the auto router."""

    text: str = Field(min_length=1)
    language: Literal["es", "en"] = "es"

    @model_validator(mode="after")
    def _require_nonempty_text(self) -> QueryResolveRequest:
        if not self.text.strip():
            raise ValueError("query text must be nonempty")
        return self


class QueryResolveResponse(_ResponseModel):
    """The selected branch plus the rationale and trace identifier."""

    decision: Literal["question", "claim", "clarification_required"]
    rationale: str | None
    trace_id: str | None

    @classmethod
    def from_domain(cls, execution: RouteExecution) -> QueryResolveResponse:
        """Project a ``RouteExecution`` into HTTP DTOs without asset paths."""

        return cls(
            decision=execution.classification.decision,
            rationale=execution.classification.rationale,
            trace_id=execution.trace_id,
        )