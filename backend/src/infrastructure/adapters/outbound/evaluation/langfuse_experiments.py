"""Narrow adapters around native Langfuse dataset experiments."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

from application.models.query import QueryExecution, QueryInput


class AnswerQuestion(Protocol):
    """Inbound capability shared by API and native evaluation tasks."""

    def execute(self, query: QueryInput) -> Awaitable[QueryExecution]: ...


class DatasetItem(Protocol):
    """Small structural view of the Langfuse SDK item passed to a task."""

    input: object


def build_question_task(
    answer_question: AnswerQuestion,
) -> Callable[..., Awaitable[dict[str, object]]]:
    """Build a task that deliberately selects only user-provided dataset input."""

    async def task(*, item: DatasetItem, **_: object) -> dict[str, object]:
        query = _query_from_dataset_input(item.input)
        execution = await answer_question.execute(query)
        return serialize_execution(execution)

    return task


def serialize_execution(execution: QueryExecution) -> dict[str, object]:
    """Keep the returned answer and delivered evidence identity, never raw pages."""

    return {
        "result": {
            "status": execution.result.status,
            "blocks": [
                {"text": block.text, "evidence_ids": list(block.evidence_ids)}
                for block in execution.result.blocks
            ],
        },
        "answer_text": "\n\n".join(block.text for block in execution.result.blocks),
        "context": [
            {
                "evidence_ids": list(item.evidence_ids),
                "delivery": item.delivery,
                "sources": [
                    {
                        "evidence_id": source.evidence_id,
                        "pdf_page": source.pdf_page,
                        "printed_label": source.printed_label,
                    }
                    for source in item.sources
                ],
            }
            for item in execution.context
        ],
        "trace_id": execution.trace_id,
    }


def _query_from_dataset_input(raw: object) -> QueryInput:
    if not isinstance(raw, dict):
        raise ValueError("Langfuse dataset input must be an object")
    text = raw.get("text")
    language = raw.get("language")
    if not isinstance(text, str) or language not in ("es", "en"):
        raise ValueError("Langfuse dataset input requires text and language")
    return QueryInput(text=text, language=language)
