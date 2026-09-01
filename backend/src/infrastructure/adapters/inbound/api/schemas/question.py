"""HTTP representations for explicit grounded document questions."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from application.models.query import QueryExecution


class _ResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class QuestionRequest(BaseModel):
    """One explicit question for the document-question use case."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str = Field(min_length=1)
    language: Literal["es", "en"] = "es"

    @model_validator(mode="after")
    def _require_nonempty_text(self) -> QuestionRequest:
        if not self.text.strip():
            raise ValueError("question text must be nonempty")
        return self


class AnswerBlockResponse(_ResponseModel):
    """One answer passage and the evidence identifiers it cites."""

    text: str
    evidence_ids: tuple[str, ...]


class ContextSourceResponse(_ResponseModel):
    """Public source identity retained from the evidence given to the question flow."""

    evidence_id: str
    document_hash: str
    pdf_page: int
    printed_label: str | None


class ContextEvidenceResponse(_ResponseModel):
    """One piece of evidence available to the generation workflow."""

    evidence_ids: tuple[str, ...]
    text: str
    delivery: Literal["text", "image", "rule"]
    sources: tuple[ContextSourceResponse, ...]


class QuestionResponse(_ResponseModel):
    """A document answer and the complete context that grounded it."""

    status: Literal["answered", "partial", "insufficient_evidence", "out_of_scope"]
    blocks: tuple[AnswerBlockResponse, ...]
    context: tuple[ContextEvidenceResponse, ...]
    trace_id: str | None

    @classmethod
    def from_domain(cls, execution: QueryExecution) -> QuestionResponse:
        """Serialize all audit-relevant output without exposing local asset paths."""

        return cls(
            status=execution.result.status,
            blocks=tuple(
                AnswerBlockResponse(text=block.text, evidence_ids=block.evidence_ids)
                for block in execution.result.blocks
            ),
            context=tuple(
                ContextEvidenceResponse(
                    evidence_ids=context.evidence_ids,
                    text=context.text,
                    delivery=context.delivery,
                    sources=tuple(
                        ContextSourceResponse(
                            evidence_id=source.evidence_id,
                            document_hash=source.document_hash,
                            pdf_page=source.pdf_page,
                            printed_label=source.printed_label,
                        )
                        for source in context.sources
                    ),
                )
                for context in execution.context
            ),
            trace_id=execution.trace_id,
        )
