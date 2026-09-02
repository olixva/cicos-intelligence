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
from typing import TYPE_CHECKING, Protocol, cast

from application.models.claim import ClaimExecution
from application.models.query import QueryExecution, QueryInput
from domain.models.claim import ClaimInput
from domain.models.routing import ClarificationResult, RouteExecution

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
    payload = cast(dict[str, object], raw)
    text = payload.get("text")
    language = payload.get("language")
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
    if not value.strip():
        raise ValueError(f"{name} must be a nonblank string")


# ---------------------------------------------------------------------------
# Claim experiment adapter
# ---------------------------------------------------------------------------


class AnalyzeClaim(Protocol):
    """Inbound capability shared by API and native claim evaluation tasks."""

    def execute(self, claim: ClaimInput) -> Awaitable[ClaimExecution]: ...


def build_claim_task(
    analyze_claim: AnalyzeClaim,
) -> Callable[..., Awaitable[dict[str, object]]]:
    """Build a task that only reads the user-provided dataset input."""

    async def task(*, item: DatasetItem, **_: object) -> dict[str, object]:
        claim = _claim_input_from_dataset_input(item.input)
        execution = await analyze_claim.execute(claim)
        return serialize_claim_execution(execution)

    return task


def serialize_claim_execution(execution: ClaimExecution) -> dict[str, object]:
    """Project a claim execution onto the schema consumed by Langfuse evaluators."""

    return {
        "result": {
            "applicability": execution.result.applicability,
            "convention": execution.result.convention,
            "decision": execution.result.decision,
            "conditions": list(execution.result.conditions),
            "missing_information": list(execution.result.missing_information),
            "needs_input": execution.needs_input,
            "interview_missing": list(execution.missing_information),
        },
        "facts": [
            {"name": fact.name, "value": fact.value, "asserted_by": fact.asserted_by}
            for fact in execution.result.facts
        ],
        "blocks": [
            {"text": block.text, "evidence_ids": list(block.evidence_ids)}
            for block in execution.result.blocks
        ],
        "context": [
            {
                "evidence_ids": list(item.evidence_ids),
                "delivery": item.delivery,
            }
            for item in execution.context
        ],
        "trace_id": execution.trace_id,
    }


def _claim_input_from_dataset_input(raw: object) -> ClaimInput:
    """Parse a Langfuse dataset item input into a validated ``ClaimInput``."""

    if not isinstance(raw, dict):
        raise ValueError("Langfuse dataset input must be an object")
    payload = cast(dict[str, object], raw)
    text = payload.get("text")
    language = payload.get("language")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Langfuse dataset input requires text")
    if language not in ("es", "en"):
        raise ValueError("Langfuse dataset input requires language in {es, en}")
    clarifications = payload.get("clarifications", ())
    if not isinstance(clarifications, (list, tuple)):
        raise ValueError("Langfuse dataset input clarifications must be a sequence")
    clarifications_tuple: tuple[str, ...] = tuple(cast(Sequence[str], clarifications))
    session_id_raw = payload.get("session_id")
    thread_id_raw = payload.get("thread_id")
    resume_raw = payload.get("resume", False)
    return ClaimInput(
        text=text,
        language=language,
        clarifications=clarifications_tuple,
        session_id=session_id_raw if isinstance(session_id_raw, str) else None,
        thread_id=thread_id_raw if isinstance(thread_id_raw, str) else None,
        resume=bool(resume_raw),
    )


def run_claim_experiment(
    profile_name: str,
    dataset_name: str,
    dataset_version: str,
    evaluators: Sequence[EvaluatorFunction],
    *,
    langfuse_client: Langfuse | None = None,
) -> ExperimentResult:
    """Run a native Langfuse claim experiment against an injected dataset client."""

    _validate_identifier("dataset_name", dataset_name)
    _validate_identifier("dataset_version", dataset_version)
    _validate_identifier("profile_name", profile_name)

    client = langfuse_client if langfuse_client is not None else _default_langfuse_client()
    from bootstrap import build_analyze_claim  # lazy import: avoid cycles

    dataset_client = client.get_dataset(dataset_name)
    analyze_claim = build_analyze_claim(profile_name)
    task = build_claim_task(analyze_claim)
    return dataset_client.run_experiment(
        name=dataset_name,
        run_name=f"{profile_name}-{dataset_version}",
        task=task,
        evaluators=list(evaluators),
        max_concurrency=_resolve_max_concurrency(),
    )


# ---------------------------------------------------------------------------
# Router experiment adapter
# ---------------------------------------------------------------------------


class ResolveQuery(Protocol):
    """Inbound capability shared by API and native router evaluation tasks."""

    def execute(self, query: QueryInput) -> Awaitable[RouteExecution]: ...


def build_router_task(
    resolve_query: ResolveQuery,
) -> Callable[..., Awaitable[dict[str, object]]]:
    """Build a task that only reads the user-provided dataset input."""

    async def task(*, item: DatasetItem, **_: object) -> dict[str, object]:
        query = _query_from_dataset_input(item.input)
        execution = await resolve_query.execute(query)
        return serialize_route_execution(execution)

    return task


def serialize_route_execution(execution: RouteExecution) -> dict[str, object]:
    """Project a route execution onto the schema consumed by Langfuse evaluators."""

    dispatch_kind, result = _dispatch_projection(execution.dispatch)
    return {
        "query_text": execution.query.text,
        "query_language": execution.query.language,
        "decision": execution.classification.decision,
        "rationale": execution.classification.rationale,
        "dispatch_kind": dispatch_kind,
        "trace_id": execution.trace_id,
        "result": result,
    }


def _dispatch_projection(
    dispatch: QueryExecution | ClaimExecution | ClarificationResult,
) -> tuple[str, dict[str, object]]:
    if isinstance(dispatch, QueryExecution):
        return (
            "question",
            {
                "status": dispatch.result.status,
                "blocks": [
                    {"text": block.text, "evidence_ids": list(block.evidence_ids)}
                    for block in dispatch.result.blocks
                ],
            },
        )
    if isinstance(dispatch, ClaimExecution):
        return (
            "claim",
            {
                "decision": dispatch.result.decision,
                "applicability": dispatch.result.applicability,
                "convention": dispatch.result.convention,
            },
        )
    # Type is narrowed to ClarificationResult by elimination; runtime guards
    # on the route execution dispatch type belong to the use case itself.
    return (
        "clarification",
        {
            "message": dispatch.message,
            "missing_fields": list(dispatch.missing_fields),
        },
    )


def run_router_experiment(
    profile_name: str,
    dataset_name: str,
    dataset_version: str,
    evaluators: Sequence[EvaluatorFunction],
    *,
    langfuse_client: Langfuse | None = None,
) -> ExperimentResult:
    """Run a native Langfuse router experiment against an injected dataset client."""

    _validate_identifier("dataset_name", dataset_name)
    _validate_identifier("dataset_version", dataset_version)
    _validate_identifier("profile_name", profile_name)

    client = langfuse_client if langfuse_client is not None else _default_langfuse_client()
    from bootstrap import build_resolve_query  # lazy import: avoid cycles

    dataset_client = client.get_dataset(dataset_name)
    resolve_query = build_resolve_query(profile_name)
    task = build_router_task(resolve_query)
    return dataset_client.run_experiment(
        name=dataset_name,
        run_name=f"{profile_name}-{dataset_version}",
        task=task,
        evaluators=list(evaluators),
        max_concurrency=_resolve_max_concurrency(),
    )
