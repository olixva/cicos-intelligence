"""Closed-enum auto-router dispatch service.

These tests pin the counter invariants the design requires: each query
runs through exactly one downstream flow. ``clarification_required``
must execute neither; an unsupported classifier output must raise
``RouteExecutionError`` before any dispatch attempt.

The repo convention runs async test bodies via ``asyncio.run`` inside
``def`` tests rather than ``async def``; we follow that pattern here.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import pytest

from application.models.claim import ClaimExecution
from application.models.query import (
    AnswerBlock,
    QueryExecution,
    QueryInput,
    QuestionAnswer,
)
from application.services.routing import (
    RouteExecutionError,
    resolve_query,
)
from domain.models.decision import ClaimAnalysis
from domain.models.routing import (
    ClarificationResult,
    RouteClassification,
)


@dataclass
class _CounterAnswerQuestion:
    calls: int = 0
    payload: QueryExecution = field(
        default_factory=lambda: QueryExecution(
            result=QuestionAnswer("answered", (AnswerBlock("ok", ("sha256:x:page:1",)),)),
            context=(),
            trace_id="trace-q",
        )
    )

    async def execute(self, query: QueryInput) -> QueryExecution:
        self.calls += 1
        return self.payload


@dataclass
class _CounterAnalyzeClaim:
    calls: int = 0
    payload: ClaimExecution = field(
        default_factory=lambda: ClaimExecution(
            result=ClaimAnalysis(
                applicability="applicable",
                convention="CIDE",
                decision="resolved",
                party_ids=("A", "B"),
                facts=(),
                contradictions=(),
                conditions=(),
                missing_information=(),
                blocks=(),
            ),
            context=(),
            trace_id="trace-c",
        )
    )

    async def execute(self, claim) -> ClaimExecution:  # type: ignore[no-untyped-def]
        self.calls += 1
        return self.payload


@dataclass
class _StubClassifier:
    classification: RouteClassification

    async def classify(self, query: QueryInput) -> RouteClassification:
        return self.classification


class _BoomAnswerQuestion:
    async def execute(self, query: QueryInput) -> QueryExecution:
        raise RuntimeError("provider exploded")


class _BoomAnalyzeClaim:
    async def execute(self, claim) -> ClaimExecution:  # type: ignore[no-untyped-def]
        raise RuntimeError("provider exploded")


def _query() -> QueryInput:
    return QueryInput(text="¿Qué dice el manual sobre CIDE?", language="es")


def test_resolve_query_dispatches_question_exactly_once() -> None:
    answer = _CounterAnswerQuestion()
    claim = _CounterAnalyzeClaim()
    classifier = _StubClassifier(RouteClassification("question"))

    execution = asyncio.run(resolve_query(_query(), classifier, answer, claim))

    assert execution.classification.decision == "question"
    assert isinstance(execution.dispatch, QueryExecution)
    assert answer.calls == 1
    assert claim.calls == 0
    assert execution.trace_id == "trace-q"


def test_resolve_query_dispatches_claim_exactly_once() -> None:
    answer = _CounterAnswerQuestion()
    claim = _CounterAnalyzeClaim()
    classifier = _StubClassifier(RouteClassification("claim"))

    execution = asyncio.run(resolve_query(_query(), classifier, answer, claim))

    assert execution.classification.decision == "claim"
    assert isinstance(execution.dispatch, ClaimExecution)
    assert answer.calls == 0
    assert claim.calls == 1
    assert execution.trace_id == "trace-c"


def test_resolve_query_clarification_executes_no_flow() -> None:
    answer = _CounterAnswerQuestion()
    claim = _CounterAnalyzeClaim()
    classifier = _StubClassifier(
        RouteClassification("clarification_required", rationale="faltan datos")
    )

    execution = asyncio.run(resolve_query(_query(), classifier, answer, claim))

    assert execution.classification.decision == "clarification_required"
    assert isinstance(execution.dispatch, ClarificationResult)
    assert execution.dispatch.message == "faltan datos"
    assert answer.calls == 0
    assert claim.calls == 0
    assert execution.trace_id is not None  # uuid synthesized


def test_resolve_query_clarification_falls_back_to_default_message() -> None:
    answer = _CounterAnswerQuestion()
    claim = _CounterAnalyzeClaim()
    classifier = _StubClassifier(RouteClassification("clarification_required"))

    execution = asyncio.run(resolve_query(_query(), classifier, answer, claim))

    assert isinstance(execution.dispatch, ClarificationResult)
    assert "Necesito más información" in execution.dispatch.message


def test_resolve_query_rejects_unsupported_decision() -> None:
    classifier = _StubClassifier(RouteClassification("nonsense"))  # type: ignore[arg-type]
    answer = _CounterAnswerQuestion()
    claim = _CounterAnalyzeClaim()

    with pytest.raises(RouteExecutionError, match="unsupported routing decision"):
        asyncio.run(resolve_query(_query(), classifier, answer, claim))


def test_resolve_query_wraps_provider_error_from_answer_flow() -> None:
    classifier = _StubClassifier(RouteClassification("question"))

    with pytest.raises(RouteExecutionError, match="routing flow raised RuntimeError"):
        asyncio.run(
            resolve_query(_query(), classifier, _BoomAnswerQuestion(), _CounterAnalyzeClaim())
        )


def test_resolve_query_wraps_provider_error_from_claim_flow() -> None:
    classifier = _StubClassifier(RouteClassification("claim"))

    with pytest.raises(RouteExecutionError, match="routing flow raised RuntimeError"):
        asyncio.run(
            resolve_query(_query(), classifier, _CounterAnswerQuestion(), _BoomAnalyzeClaim())
        )
