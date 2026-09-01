"""Narrow adapters around native Langfuse dataset experiments.

This module targets ``langfuse==4.15.1``. The public
``DatasetClient.run_experiment`` signature in that version is keyword-only;
the adapter below calls it exclusively with keyword arguments and never
relies on positional order.

The adapter does not introduce a parallel runner: it composes the existing
``build_question_task`` task, the shared ``serialize_execution`` serializer,
and the live ``build_answer_question`` factory through their application
ports. Default concurrency is 4 (controlled via the
``ALLIANZ_LANGFUSE_MAX_CONCURRENCY`` environment variable); the Langfuse SDK
default of 50 is intentionally never used.
"""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable, Sequence
from typing import TYPE_CHECKING, Protocol

from application.models.query import QueryExecution, QueryInput

if TYPE_CHECKING:
    from langfuse import Langfuse
    from langfuse.experiment import EvaluatorFunction, ExperimentResult

_DEFAULT_MAX_CONCURRENCY = 4

# Module-level handle for the production default. The ``Langfuse`` instance
# is created lazily on first use so importing this module does not print
# authentication warnings when tests run without Langfuse credentials.
# Tests inject a fake client through the ``langfuse_client`` keyword argument
# so they do not have to monkeypatch module globals.
langfuse: Langfuse | None = None


def _default_langfuse_client() -> Langfuse:
    global langfuse
    if langfuse is None:
        from langfuse import Langfuse as _Langfuse

        langfuse = _Langfuse()
    return langfuse


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


def _resolve_max_concurrency() -> int:
    """Resolve the per-experiment concurrency budget from the environment.

    Defaults to 4 to match the local budget chosen for the test fixtures; the
    Langfuse SDK default of 50 is never used. Empty strings and unparseable
    values raise a clear ``ValueError`` rather than silently falling back.
    """

    raw = os.environ.get("ALLIANZ_LANGFUSE_MAX_CONCURRENCY", "").strip()
    if not raw:
        return _DEFAULT_MAX_CONCURRENCY
    try:
        value = int(raw)
    except ValueError as error:
        raise ValueError(
            f"ALLIANZ_LANGFUSE_MAX_CONCURRENCY must be a positive integer, got {raw!r}"
        ) from error
    if value <= 0:
        raise ValueError(
            f"ALLIANZ_LANGFUSE_MAX_CONCURRENCY must be a positive integer, got {value}"
        )
    return value


def run_question_experiment(
    profile_name: str,
    dataset_name: str,
    dataset_version: str,
    evaluators: Sequence[EvaluatorFunction],
    *,
    langfuse_client: Langfuse | None = None,
) -> ExperimentResult:
    """Run a native Langfuse question experiment against an injected dataset client.

    The dataset client defaults to the module-level ``langfuse`` handle.
    Production callers (see ``bootstrap.build_question_experiment_runner``)
    inject the live client explicitly so tests can substitute fakes without
    monkeypatching module globals.

    The ``DatasetClient.run_experiment`` call uses keyword arguments only
    because of the ``langfuse==4.15.1`` SDK contract.
    """

    _validate_identifier("dataset_name", dataset_name)
    _validate_identifier("dataset_version", dataset_version)
    _validate_identifier("profile_name", profile_name)

    client = langfuse_client if langfuse_client is not None else _default_langfuse_client()
    from bootstrap import build_answer_question  # lazy import: avoid cycles

    dataset_client = client.get_dataset(dataset_name)
    answer_question = build_answer_question(profile_name)
    task = build_question_task(answer_question)
    return dataset_client.run_experiment(
        name=dataset_name,
        run_name=f"{profile_name}-{dataset_version}",
        task=task,
        evaluators=list(evaluators),
        max_concurrency=_resolve_max_concurrency(),
    )


def _validate_identifier(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonblank string")
