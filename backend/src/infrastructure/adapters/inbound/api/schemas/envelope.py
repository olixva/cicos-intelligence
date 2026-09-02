"""Common request and response envelope for the unified API surface.

The envelope unifies the three modes (question, claim, auto) and the
streaming variant without changing the contract of the explicit
question and claim routes already mounted by ``routes/questions.py``
and ``routes/claims.py``. The envelope route is additive; the
explicit routes remain valid for callers that want minimal responses.

Request:

    {
        "text": "...",
        "language": "es" | "en",
        "mode": "question" | "claim" | "auto",
        "profile": "<catalog-profile>" | null,
        "clarifications": ["..."] (claim only, optional),
        "stream": bool
    }

Response (synchronous):

    {
        "request_id": "<uuid4>",
        "requested_mode": "...",
        "resolved_mode": "question" | "claim" | "clarification",
        "result": { "kind": "question" | "claim" | "clarification", ... },
        "evidence": [ ... ],
        "metadata": { "trace_id": "..." }
    }

The explicit ``mode`` dispatch rule (per Oracle Gate 1): ``question``
goes straight to ``AnswerQuestion`` and never invokes the auto
router; ``claim`` goes straight to ``AnalyzeClaim`` and never invokes
the auto router; ``auto`` invokes ``ResolveQuery`` and the response's
``resolved_mode`` reflects the selector outcome.
"""

from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from application.models.claim import ClaimExecution
from application.models.query import QueryExecution
from domain.models.decision import ClaimAnalysis
from domain.models.routing import ClarificationResult, RouteExecution


def _langfuse_trace_url(trace_id: str) -> str:
    """Build the public Langfuse URL for ``trace_id`` from env-driven config.

    ``LANGFUSE_PUBLIC_URL`` (preferred) is the URL the browser opens;
    ``LANGFUSE_BASE_URL`` is the SDK-internal endpoint and may differ.
    Falls back to a relative ``/trace/<id>`` link when neither is set so
    the field is always present in the envelope payload.
    """

    base = os.environ.get("LANGFUSE_PUBLIC_URL") or os.environ.get("LANGFUSE_BASE_URL", "")
    base = base.strip().rstrip("/")
    if not base:
        return f"/trace/{trace_id}"
    return f"{base}/trace/{trace_id}"


class _ResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EnvelopeRequest(_ResponseModel):
    """One unified request across the three modes.

    ``mode`` selects the explicit flow; ``profile`` optionally
    overrides the composition-root default. The route validates that
    ``clarifications`` is only supplied for ``claim`` mode.
    """

    text: str = Field(min_length=1)
    language: Literal["es", "en"] = "es"
    mode: Literal["question", "claim", "auto"]
    profile: str | None = None
    clarifications: tuple[str, ...] | None = None
    stream: bool = False

    @model_validator(mode="after")
    def _require_nonblank_text(self) -> EnvelopeRequest:
        if not self.text.strip():
            raise ValueError("envelope text must be nonempty")
        if self.clarifications is not None:
            if self.mode != "claim":
                raise ValueError("clarifications are only allowed when mode is 'claim'")
            for item in self.clarifications:
                if not isinstance(item, str) or not item.strip():
                    raise ValueError("each clarification must be a nonempty string")
        return self


class EvidenceItem(_ResponseModel):
    """One piece of evidence exposed in the envelope (no asset paths).

    Field names mirror the canonical evidence schema
    (``schemas/evidence.py:31-40``): ``document_hash`` and ``pdf_page``.
    No ``version`` field because ``PageEvidence`` does not carry one;
    the document hash already pins the version.
    """

    evidence_id: str
    document_hash: str
    pdf_page: int
    delivery: Literal["text", "image", "rule"] = "text"


class QuestionResult(_ResponseModel):
    """The synchronous question branch."""

    kind: Literal["question"]
    status: Literal["answered", "partial", "insufficient_evidence", "out_of_scope"]
    blocks: tuple[dict[str, object], ...] = ()
    trace_id: str | None = None


class ClaimResult(_ResponseModel):
    """The synchronous claim branch (subset, no asset paths)."""

    kind: Literal["claim"]
    applicability: Literal["applicable", "not_applicable", "undetermined"]
    convention: Literal["CIDE", "ASCIDE"] | None
    decision: Literal["resolved", "conditional", "undetermined", "not_assessed"]
    trace_id: str | None = None


class ClarificationResultBody(_ResponseModel):
    """The auto-router branch when the classifier asks for more input."""

    kind: Literal["clarification"]
    message: str
    missing_fields: tuple[str, ...] = ()


class EnvelopeResponse(_ResponseModel):
    """The unified response shape across the three modes."""

    request_id: str
    requested_mode: Literal["question", "claim", "auto"]
    resolved_mode: Literal["question", "claim", "clarification"]
    result: QuestionResult | ClaimResult | ClarificationResultBody
    evidence: tuple[EvidenceItem, ...] = ()
    metadata: dict[str, str] = {}

    @classmethod
    def from_question(
        cls,
        *,
        request_id: str,
        execution: QueryExecution,
        evidence: tuple[EvidenceItem, ...] = (),
    ) -> EnvelopeResponse:
        trace_id = execution.trace_id or ""
        return cls(
            request_id=request_id,
            requested_mode="question",
            resolved_mode="question",
            result=QuestionResult(
                kind="question",
                status=execution.result.status,
                blocks=tuple(
                    {"text": block.text, "evidence_ids": list(block.evidence_ids)}
                    for block in execution.result.blocks
                ),
                trace_id=execution.trace_id,
            ),
            evidence=evidence,
            metadata={
                "trace_id": trace_id,
                "langfuse_url": _langfuse_trace_url(trace_id),
            },
        )

    @classmethod
    def from_claim(
        cls,
        *,
        request_id: str,
        execution: ClaimExecution,
        evidence: tuple[EvidenceItem, ...] = (),
    ) -> EnvelopeResponse:
        analysis = execution.result
        if not isinstance(analysis, ClaimAnalysis):
            raise TypeError("envelope.from_claim requires a ClaimAnalysis result")
        trace_id = execution.trace_id or ""
        return cls(
            request_id=request_id,
            requested_mode="claim",
            resolved_mode="claim",
            result=ClaimResult(
                kind="claim",
                applicability=analysis.applicability,
                convention=analysis.convention,
                decision=analysis.decision,
                trace_id=execution.trace_id,
            ),
            evidence=evidence,
            metadata={
                "trace_id": trace_id,
                "langfuse_url": _langfuse_trace_url(trace_id),
            },
        )

    @classmethod
    def from_clarification(
        cls,
        *,
        request_id: str,
        execution: RouteExecution,
    ) -> EnvelopeResponse:
        dispatch = execution.dispatch
        if not isinstance(dispatch, ClarificationResult):
            raise TypeError("envelope.from_clarification requires a ClarificationResult dispatch")
        trace_id = execution.trace_id or ""
        return cls(
            request_id=request_id,
            requested_mode="auto",
            resolved_mode="clarification",
            result=ClarificationResultBody(
                kind="clarification",
                message=dispatch.message,
                missing_fields=dispatch.missing_fields,
            ),
            evidence=(),
            metadata={
                "trace_id": trace_id,
                "langfuse_url": _langfuse_trace_url(trace_id),
                "decision": execution.classification.decision,
            },
        )

    @classmethod
    def from_route_execution(
        cls,
        *,
        request_id: str,
        execution: RouteExecution,
        evidence: tuple[EvidenceItem, ...] = (),
    ) -> EnvelopeResponse:
        """Project an auto-router execution into the envelope.

        ``requested_mode`` is hardcoded to ``auto`` because the caller
        asked for the router; ``resolved_mode`` reflects the dispatch
        type the router chose.
        """

        from application.models.query import QueryExecution

        dispatch = execution.dispatch
        trace_id = execution.trace_id or ""
        if isinstance(dispatch, QueryExecution):
            return cls(
                request_id=request_id,
                requested_mode="auto",
                resolved_mode="question",
                result=QuestionResult(
                    kind="question",
                    status=dispatch.result.status,
                    blocks=tuple(
                        {"text": block.text, "evidence_ids": list(block.evidence_ids)}
                        for block in dispatch.result.blocks
                    ),
                    trace_id=dispatch.trace_id,
                ),
                evidence=evidence,
                metadata={
                    "trace_id": trace_id,
                    "langfuse_url": _langfuse_trace_url(trace_id),
                },
            )
        if isinstance(dispatch, ClaimExecution):
            analysis = dispatch.result
            if not isinstance(analysis, ClaimAnalysis):
                raise TypeError("envelope.from_route_execution requires ClaimAnalysis result")
            return cls(
                request_id=request_id,
                requested_mode="auto",
                resolved_mode="claim",
                result=ClaimResult(
                    kind="claim",
                    applicability=analysis.applicability,
                    convention=analysis.convention,
                    decision=analysis.decision,
                    trace_id=dispatch.trace_id,
                ),
                evidence=evidence,
                metadata={
                    "trace_id": trace_id,
                    "langfuse_url": _langfuse_trace_url(trace_id),
                },
            )
        if isinstance(dispatch, ClarificationResult):
            return cls(
                request_id=request_id,
                requested_mode="auto",
                resolved_mode="clarification",
                result=ClarificationResultBody(
                    kind="clarification",
                    message=dispatch.message,
                    missing_fields=dispatch.missing_fields,
                ),
                evidence=(),
                metadata={
                    "trace_id": trace_id,
                    "langfuse_url": _langfuse_trace_url(trace_id),
                    "decision": execution.classification.decision,
                },
            )
        raise TypeError(f"unsupported dispatch type: {type(dispatch).__name__}")
