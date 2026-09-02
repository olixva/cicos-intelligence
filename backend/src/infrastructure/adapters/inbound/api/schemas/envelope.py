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
from domain.models.claim import ClaimFact
from domain.models.decision import ClaimAnalysis
from domain.models.routing import ClarificationResult, RouteExecution


def _langfuse_trace_url(trace_id: str) -> str | None:
    """Build a Langfuse trace URL from env config, or return ``None``.

    A Langfuse trace lives at ``{base}/project/{project_id}/traces/{trace_id}``.
    The older shape ``{base}/trace/{trace_id}`` is not a real route and lands
    the user on "trace not found", so it is never emitted: a link that
    reliably 404s is worse than no link at all.

    This helper is only the fallback. The canonical URL comes from the SDK's
    ``get_trace_url()``, carried on the execution, which knows the project
    without any extra configuration.

    ``LANGFUSE_PUBLIC_URL`` (what the browser opens) is preferred over
    ``LANGFUSE_BASE_URL`` (the SDK endpoint), since the two may differ.
    """

    base = os.environ.get("LANGFUSE_PUBLIC_URL") or os.environ.get("LANGFUSE_BASE_URL", "")
    base = base.strip().rstrip("/")
    project_id = os.environ.get("LANGFUSE_PROJECT_ID", "").strip()
    if not base or not project_id or not trace_id.strip():
        return None
    return f"{base}/project/{project_id}/traces/{trace_id}"


def _claim_result(analysis: ClaimAnalysis, execution: ClaimExecution) -> ClaimResult:
    """Project a claim analysis into the wire result.

    Both the explicit claim endpoint and the auto-router branch go through
    here. They used to build ``ClaimResult`` separately, and the router copy
    was never extended, so auto - the default mode - silently returned an
    answer stripped of its facts, conditions and explanation blocks.
    """

    return ClaimResult(
        kind="claim",
        applicability=analysis.applicability,
        convention=analysis.convention,
        decision=analysis.decision,
        party_ids=analysis.party_ids,
        facts=tuple(_claim_fact(fact) for fact in analysis.facts),
        contradictions=tuple(
            {
                "fact_name": contradiction.fact_name,
                "statements": tuple(
                    _claim_fact(statement) for statement in contradiction.statements
                ),
            }
            for contradiction in analysis.contradictions
        ),
        conditions=analysis.conditions,
        missing_information=analysis.missing_information,
        blocks=tuple(
            {"text": block.text, "evidence_ids": block.evidence_ids} for block in analysis.blocks
        ),
        rules_evaluated=tuple(
            {
                "rule_id": evaluation.rule_id,
                "result": evaluation.result,
                "inputs": tuple({"name": k, "value": v} for k, v in evaluation.inputs),
                "evidence_ids": evaluation.evidence_ids,
                "rationale": evaluation.rationale,
            }
            for evaluation in analysis.rules_evaluated
        ),
        trace_id=execution.trace_id,
        trace_url=execution.trace_url or _langfuse_trace_url(execution.trace_id or ""),
    )


def _claim_fact(fact: ClaimFact) -> dict[str, object]:
    """Serialize one extracted fact, keeping who asserted it and its literal origin.

    ``asserted_by`` is what separates a claim made by one driver from a fact
    both accept, so it never gets flattened away.
    """

    return {
        "name": fact.name,
        "value": fact.value,
        "asserted_by": fact.asserted_by,
        "source_text": fact.source_text,
    }


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
    session_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _require_nonblank_text(self) -> EnvelopeRequest:
        if not self.text.strip():
            raise ValueError("envelope text must be nonempty")
        if self.clarifications is not None:
            if self.mode != "claim":
                raise ValueError("clarifications are only allowed when mode is 'claim'")
            for item in self.clarifications:
                if not item.strip():
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
    trace_url: str | None = None


class ClaimResult(_ResponseModel):
    """The synchronous claim branch, without asset paths.

    The three enum fields alone are unreadable: "applicability=undetermined,
    decision=conditional" tells a user nothing about what was established,
    what is missing or which page supports it. The reasoning the domain
    already computed travels with them.
    """

    kind: Literal["claim"]
    applicability: Literal["applicable", "not_applicable", "undetermined"]
    convention: Literal["CIDE", "ASCIDE"] | None
    decision: Literal["resolved", "conditional", "undetermined", "not_assessed"]
    party_ids: tuple[str, ...] = ()
    facts: tuple[dict[str, object], ...] = ()
    contradictions: tuple[dict[str, object], ...] = ()
    conditions: tuple[str, ...] = ()
    missing_information: tuple[str, ...] = ()
    blocks: tuple[dict[str, object], ...] = ()
    #: Every rule the deterministic engine ran, with its inputs, its outcome
    #: and the manual pages behind it. Never a placeholder.
    rules_evaluated: tuple[dict[str, object], ...] = ()
    trace_id: str | None = None
    trace_url: str | None = None


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
    # ``langfuse_url`` is None whenever no real trace URL can be built; the
    # frontend hides the link rather than offering one that 404s.
    metadata: dict[str, str | None] = {}

    @classmethod
    def from_question(
        cls,
        *,
        request_id: str,
        execution: QueryExecution,
        evidence: tuple[EvidenceItem, ...] = (),
    ) -> EnvelopeResponse:
        trace_id = execution.trace_id or ""
        trace_url = execution.trace_url or _langfuse_trace_url(trace_id)
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
                trace_url=trace_url,
            ),
            evidence=evidence,
            metadata={
                "trace_id": trace_id,
                "langfuse_url": trace_url,
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
        trace_id = execution.trace_id or ""
        trace_url = execution.trace_url or _langfuse_trace_url(trace_id)
        return cls(
            request_id=request_id,
            requested_mode="claim",
            resolved_mode="claim",
            result=_claim_result(analysis, execution),
            evidence=evidence,
            metadata={
                "trace_id": trace_id,
                "langfuse_url": trace_url,
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
                    trace_url=dispatch.trace_url or _langfuse_trace_url(dispatch.trace_id or ""),
                ),
                evidence=evidence,
                metadata={
                    "trace_id": trace_id,
                    "langfuse_url": _langfuse_trace_url(trace_id),
                },
            )
        if isinstance(dispatch, ClaimExecution):
            analysis = dispatch.result
            return cls(
                request_id=request_id,
                requested_mode="auto",
                resolved_mode="claim",
                result=_claim_result(analysis, dispatch),
                evidence=evidence,
                metadata={
                    "trace_id": trace_id,
                    "langfuse_url": _langfuse_trace_url(trace_id),
                },
            )
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
