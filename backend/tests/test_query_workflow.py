"""LangGraph closed-enum selector end-to-end tests.

Each test runs a real ``StateGraph.ainvoke`` via ``asyncio.run`` against
explicit fakes; no live OpenAI, Langfuse or Qdrant is touched. The
counter invariants established in ``test_query_routing.py`` are mirrored
here at the graph-level dispatch boundary.

The repo convention runs async test bodies via ``asyncio.run`` inside
``def`` tests rather than ``async def``; we follow that pattern here.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from application.models.claim import ClaimExecution
from application.models.query import (
    AnswerBlock,
    QueryExecution,
    QueryInput,
    QuestionAnswer,
)
from domain.models.decision import ClaimAnalysis
from domain.models.routing import (
    ClarificationResult,
    RouteClassification,
)
from infrastructure.adapters.outbound.query_workflow.langgraph_workflow import (
    LangGraphResolveQuery,
    build_resolve_query_workflow,
    routing_metadata,
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


def _query() -> QueryInput:
    return QueryInput(text="texto de prueba", language="es")


def test_build_resolve_query_workflow_compiles() -> None:
    workflow = build_resolve_query_workflow(
        classifier=_StubClassifier(RouteClassification("question")),
        answer_question=_CounterAnswerQuestion(),
        analyze_claim=_CounterAnalyzeClaim(),
    )
    assert isinstance(workflow, LangGraphResolveQuery)


def test_graph_routes_question_branch() -> None:
    answer = _CounterAnswerQuestion()
    claim = _CounterAnalyzeClaim()
    workflow = build_resolve_query_workflow(
        classifier=_StubClassifier(RouteClassification("question")),
        answer_question=answer,
        analyze_claim=claim,
    )
    execution = asyncio.run(workflow.execute(_query()))

    assert execution.classification.decision == "question"
    assert isinstance(execution.dispatch, QueryExecution)
    assert answer.calls == 1
    assert claim.calls == 0


def test_graph_routes_claim_branch() -> None:
    answer = _CounterAnswerQuestion()
    claim = _CounterAnalyzeClaim()
    workflow = build_resolve_query_workflow(
        classifier=_StubClassifier(RouteClassification("claim")),
        answer_question=answer,
        analyze_claim=claim,
    )
    execution = asyncio.run(workflow.execute(_query()))

    assert execution.classification.decision == "claim"
    assert isinstance(execution.dispatch, ClaimExecution)
    assert answer.calls == 0
    assert claim.calls == 1


def test_graph_routes_clarification_branch() -> None:
    answer = _CounterAnswerQuestion()
    claim = _CounterAnalyzeClaim()
    workflow = build_resolve_query_workflow(
        classifier=_StubClassifier(
            RouteClassification("clarification_required", rationale="necesito datos")
        ),
        answer_question=answer,
        analyze_claim=claim,
    )
    execution = asyncio.run(workflow.execute(_query()))

    assert execution.classification.decision == "clarification_required"
    assert isinstance(execution.dispatch, ClarificationResult)
    assert execution.dispatch.message == "necesito datos"
    assert answer.calls == 0
    assert claim.calls == 0


def test_routing_metadata_defaults_match_module_state() -> None:
    """The module-level ``_ROUTING_METADATA`` captures the env at import time."""

    metadata = routing_metadata()
    assert metadata["langfuse_prompt_name"] == "auto-router"
    assert isinstance(metadata["langfuse_prompt_version"], int)
    assert metadata["langfuse_prompt_version"] >= 1
    assert isinstance(metadata["model_name"], str)
    assert metadata["model_name"] != ""