"""HTTP representations for the explicit convention-claim analysis route.

The DTOs intentionally mirror the closed ``ClaimAnalysis`` and
``ClaimExecution`` shapes from the domain and application layers without
importing the domain module; the module-level ``from_domain`` mapper is the
single bridge between the two layers, matching the accepted pattern in
``schemas/evidence.py`` and the ``from_domain`` mapper in
``schemas/question.py``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from application.models.claim import ClaimExecution
from domain.models.evidence import PageEvidence


class _ResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ClaimAnalysisRequest(BaseModel):
    """One explicit user narrative for the convention-claim use case."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str = Field(min_length=1)
    language: Literal["es", "en"] = "es"
    clarifications: list[str] | None = None

    @model_validator(mode="after")
    def _require_nonempty_text(self) -> ClaimAnalysisRequest:
        if not self.text.strip():
            raise ValueError("claim text must be nonempty")
        if self.clarifications is not None:
            for item in self.clarifications:
                if not item.strip():
                    raise ValueError("claim clarifications must be nonempty strings")
        return self


class ClaimFactResponse(_ResponseModel):
    """One attributed statement extracted from the user narrative."""

    name: str
    value: str | None
    asserted_by: str | None
    source_text: str


class ClaimContradictionResponse(_ResponseModel):
    """Incompatible attributed statements that never collapse into a shared fact."""

    fact_name: str
    statements: tuple[ClaimFactResponse, ...]


class ClaimEvidenceBlockResponse(_ResponseModel):
    """One claim explanation passage and its immutable supporting evidence IDs."""

    text: str
    evidence_ids: tuple[str, ...]


class RegionResponse(_ResponseModel):
    """One normalized region expressed in PDF viewport coordinates."""

    x0: float = Field(ge=0.0, le=1.0)
    y0: float = Field(ge=0.0, le=1.0)
    x1: float = Field(ge=0.0, le=1.0)
    y1: float = Field(ge=0.0, le=1.0)


class DeliveredContextResponse(_ResponseModel):
    """One piece of evidence available to the claim workflow.

    ``context_id``, ``document_id``, ``version``, ``page`` and ``region`` are
    the audit-relevant public fields. Local asset paths (for example
    ``image_path``) are deliberately omitted; the claim flow must never
    expose filesystem locations.
    """

    context_id: str
    document_id: str
    version: str
    page: int
    region: RegionResponse | None


class ClaimAnalysisResponse(_ResponseModel):
    """A bounded convention assessment distinct from a general liability opinion."""

    applicability: Literal["applicable", "not_applicable", "undetermined"]
    convention: Literal["CIDE", "ASCIDE"] | None
    decision: Literal["resolved", "conditional", "undetermined", "not_assessed"]
    parties: tuple[str, ...]
    attributed_facts: tuple[ClaimFactResponse, ...]
    contradictions: tuple[ClaimContradictionResponse, ...]
    conditions: tuple[str, ...]
    missing_information: tuple[str, ...]
    evidence_blocks: tuple[ClaimEvidenceBlockResponse, ...]
    delivered_context: tuple[DeliveredContextResponse, ...]
    trace_id: str | None

    @classmethod
    def from_domain(cls, execution: ClaimExecution) -> ClaimAnalysisResponse:
        """Map a domain ``ClaimExecution`` onto the HTTP DTO without leaking asset paths."""

        result = execution.result
        return cls(
            applicability=result.applicability,
            convention=result.convention,
            decision=result.decision,
            parties=tuple(result.party_ids),
            attributed_facts=tuple(
                ClaimFactResponse(
                    name=fact.name,
                    value=fact.value,
                    asserted_by=fact.asserted_by,
                    source_text=fact.source_text,
                )
                for fact in result.facts
            ),
            contradictions=tuple(
                ClaimContradictionResponse(
                    fact_name=contradiction.fact_name,
                    statements=tuple(
                        ClaimFactResponse(
                            name=statement.name,
                            value=statement.value,
                            asserted_by=statement.asserted_by,
                            source_text=statement.source_text,
                        )
                        for statement in contradiction.statements
                    ),
                )
                for contradiction in result.contradictions
            ),
            conditions=tuple(result.conditions),
            missing_information=tuple(result.missing_information),
            evidence_blocks=tuple(
                ClaimEvidenceBlockResponse(text=block.text, evidence_ids=tuple(block.evidence_ids))
                for block in result.blocks
            ),
            delivered_context=tuple(
                _delivered_context(context_id, source)
                for context_id, source in _iter_delivered_sources(execution)
            ),
            trace_id=execution.trace_id,
        )


def _iter_delivered_sources(execution: ClaimExecution):
    """Yield one ``(context_id, source)`` pair per delivered evidence source.

    The convention-claim flow exposes only the first source of every context
    payload; the remaining sources are reachable through the evidence-block
    ``evidence_ids`` list, which never references filesystem paths.
    """

    for context in execution.context:
        if not context.evidence_ids:
            continue
        context_id = context.evidence_ids[0]
        if context.sources:
            yield context_id, context.sources[0]


def _delivered_context(context_id: str, source: PageEvidence) -> DeliveredContextResponse:
    document_id = source.document_hash
    region = _normalize_region(source)
    return DeliveredContextResponse(
        context_id=context_id,
        document_id=document_id,
        version=document_id,
        page=source.pdf_page,
        region=region,
    )


def _normalize_region(source: PageEvidence) -> RegionResponse | None:
    if not source.regions:
        return None
    if source.width is None or source.height is None or source.width <= 0 or source.height <= 0:
        return None
    x0, y0, x1, y1 = source.regions[0]
    if not (0.0 <= x0 <= x1 <= source.width and 0.0 <= y0 <= y1 <= source.height):
        return None
    return RegionResponse(
        x0=x0 / source.width,
        y0=y0 / source.height,
        x1=x1 / source.width,
        y1=y1 / source.height,
    )
