"""Closed-enum LangGraph selector for the auto router."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from typing import NotRequired, Required, TypedDict, cast

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from application.models.claim import ClaimExecution
from application.models.query import QueryExecution, QueryInput
from application.ports.inbound.analyze_claim import AnalyzeClaim
from application.ports.inbound.answer_question import AnswerQuestion
from application.ports.outbound.query_classifier import QueryClassifier
from application.services.routing import RouteExecutionError
from domain.models.claim import ClaimInput
from domain.models.routing import (
    ClarificationResult,
    RouteClassification,
    RouteDecision,
    RouteExecution,
)

_DEFAULT_CLARIFICATION = "Necesito más información para enrutar tu consulta."
_CLOSED_DECISIONS: tuple[RouteDecision, ...] = (
    "question",
    "claim",
    "clarification_required",
)
_ROUTING_METADATA: dict[str, str | int] = {
    "langfuse_prompt_name": "auto-router",
    "langfuse_prompt_version": int(os.environ.get("ALLIANZ_ROUTER_PROMPT_VERSION", "1")),
    "model_name": os.environ.get("ALLIANZ_ROUTER_MODEL", "gpt-5.4"),
}


def routing_metadata() -> dict[str, str | int]:
    """Return a copy of the prompt/model identity captured at module import."""
    return dict(_ROUTING_METADATA)


def _question_workflow_timeout_default() -> float:
    from infrastructure.adapters.outbound.question_workflow.langgraph_workflow import (
        LangGraphQuestionWorkflow,
    )

    return _init_default(LangGraphQuestionWorkflow)


def _claim_workflow_timeout_default() -> float:
    from infrastructure.adapters.outbound.claim_workflow.langgraph_workflow import (
        LangGraphClaimWorkflow,
    )

    return _init_default(LangGraphClaimWorkflow)


def _init_default(cls: type) -> float:
    import inspect

    value = inspect.signature(cls.__init__).parameters["timeout_seconds"].default
    return float(value)


# The routing workflow's ``asyncio.timeout`` wraps classification AND the whole
# dispatched workflow, so its budget has to be larger than the budget of the
# workflow it contains. It used to be 20s while the question workflow allows
# 45s and the claim workflow 30s, so auto mode could never spend the time the
# inner workflow was entitled to and failed with "routing workflow timed out".
# Derived from the inner defaults plus a margin for the classification itself.
_CLASSIFICATION_BUDGET_SECONDS = 15.0
DEFAULT_ROUTING_TIMEOUT_SECONDS = (
    max(
        _question_workflow_timeout_default(),
        _claim_workflow_timeout_default(),
    )
    + _CLASSIFICATION_BUDGET_SECONDS
)


class RouteDispatchTimeoutError(TimeoutError):
    """The complete dispatch graph exceeded its local execution budget."""


type _DispatchResult = QueryExecution | ClaimExecution | ClarificationResult


class _RoutingState(TypedDict, total=False):
    query: Required[QueryInput]
    classification: NotRequired[RouteClassification]
    dispatch: NotRequired[_DispatchResult]


class _RoutingUpdate(TypedDict, total=False):
    classification: RouteClassification
    dispatch: _DispatchResult


def _route_decision(state: _RoutingState) -> RouteDecision:
    classification = state.get("classification")
    if classification is None:
        raise RouteExecutionError("routing workflow reached dispatch without a classification")
    decision = classification.decision
    if decision not in _CLOSED_DECISIONS:
        raise RouteExecutionError(
            f"unsupported routing decision: {decision!r}; expected one of {_CLOSED_DECISIONS}"
        )
    return decision


class LangGraphResolveQuery:
    """LangGraph state machine that selects exactly one downstream flow per query."""

    def __init__(
        self,
        *,
        classifier: QueryClassifier,
        answer_question: AnswerQuestion,
        analyze_claim: AnalyzeClaim,
        trace_id_factory: Callable[[], str | None] | None = None,
        callback_factory: Callable[[str], BaseCallbackHandler] | None = None,
        timeout_seconds: float = DEFAULT_ROUTING_TIMEOUT_SECONDS,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._classifier = classifier
        self._answer_question = answer_question
        self._analyze_claim = analyze_claim
        # Sin factory no hay traza. El default anterior fabricaba un
        # ``uuid.uuid4()``, que Langfuse rechaza por no ser 32 hex en
        # minúscula: la SDK lo descartaba y el sobre publicaba un enlace que
        # nunca podía resolver. Igual que en los otros dos workflows, la
        # ausencia de configuración se representa con ``None``.
        self._trace_id_factory: Callable[[], str | None] = trace_id_factory or (lambda: None)
        self._callback_factory = callback_factory
        self._timeout_seconds = timeout_seconds
        self._graph = self._build_graph()

    def _build_graph(self):  # pyright: ignore[reportUnknownParameterType]
        g = StateGraph(_RoutingState)
        g.add_node("classify", self._classify)  # pyright: ignore[reportUnknownMemberType]
        g.add_node("dispatch", self._dispatch)  # pyright: ignore[reportUnknownMemberType]
        g.add_node("to_question", self._to_question)  # pyright: ignore[reportUnknownMemberType]
        g.add_node("to_claim", self._to_claim)  # pyright: ignore[reportUnknownMemberType]
        g.add_node("to_clarification", self._to_clarification)  # pyright: ignore[reportUnknownMemberType]
        g.add_node("wrap", self._wrap)  # pyright: ignore[reportUnknownMemberType]
        g.add_edge(START, "classify")  # pyright: ignore[reportUnknownMemberType]
        g.add_edge("classify", "dispatch")  # pyright: ignore[reportUnknownMemberType]
        # path_map keys must equal the closed enum; unknown decisions raise in
        # _route_decision before the graph ever routes anywhere.
        g.add_conditional_edges(  # pyright: ignore[reportUnknownMemberType]
            "dispatch",
            _route_decision,
            {
                "question": "to_question",
                "claim": "to_claim",
                "clarification_required": "to_clarification",
            },
        )
        for branch in ("to_question", "to_claim", "to_clarification"):
            g.add_edge(branch, "wrap")  # pyright: ignore[reportUnknownMemberType]
        g.add_edge("wrap", END)  # pyright: ignore[reportUnknownMemberType]
        return g.compile()  # pyright: ignore[reportUnknownMemberType]

    async def execute(self, query: QueryInput) -> RouteExecution:
        trace_id = self._trace_id_factory()
        config = RunnableConfig(recursion_limit=8)
        if trace_id is not None and self._callback_factory is not None:
            config["callbacks"] = [self._callback_factory(trace_id)]  # type: ignore[arg-type]
        try:
            async with asyncio.timeout(self._timeout_seconds):
                raw = await self._graph.ainvoke(  # pyright: ignore[reportUnknownMemberType]
                    _RoutingState(query=query),
                    config=config,  # type: ignore[arg-type]
                )
        except TimeoutError as error:
            raise RouteDispatchTimeoutError("routing workflow timed out") from error
        state = cast(_RoutingState, raw)
        dispatch = state.get("dispatch")
        classification = state.get("classification")
        if dispatch is None or classification is None:
            raise RuntimeError("routing workflow completed without a dispatch")
        return RouteExecution(
            query=query,
            classification=classification,
            dispatch=dispatch,
            trace_id=trace_id,
        )

    async def _classify(self, state: _RoutingState) -> _RoutingUpdate:
        return _RoutingUpdate(classification=await self._classifier.classify(state["query"]))

    async def _dispatch(self, state: _RoutingState) -> _RoutingUpdate:
        # Anchor node: holds the conditional edge; never produces dispatch.
        return _RoutingUpdate()

    async def _to_question(self, state: _RoutingState) -> _RoutingUpdate:
        return _RoutingUpdate(dispatch=await self._answer_question.execute(state["query"]))

    async def _to_claim(self, state: _RoutingState) -> _RoutingUpdate:
        query = state["query"]
        return _RoutingUpdate(
            dispatch=await self._analyze_claim.execute(
                ClaimInput(text=query.text, language=query.language, clarifications=())
            )
        )

    async def _to_clarification(self, state: _RoutingState) -> _RoutingUpdate:
        classification = state.get("classification")
        rationale = classification.rationale if classification is not None else None
        return _RoutingUpdate(
            dispatch=ClarificationResult(message=rationale or _DEFAULT_CLARIFICATION)
        )

    async def _wrap(self, state: _RoutingState) -> _RoutingUpdate:
        dispatch = state.get("dispatch")
        if dispatch is None:
            raise RuntimeError("routing workflow reached wrap without a dispatch")
        return _RoutingUpdate(dispatch=dispatch)


def build_resolve_query_workflow(
    *,
    classifier: QueryClassifier,
    answer_question: AnswerQuestion,
    analyze_claim: AnalyzeClaim,
    trace_id_factory: Callable[[], str | None] | None = None,
    callback_factory: Callable[[str], BaseCallbackHandler] | None = None,
    timeout_seconds: float = DEFAULT_ROUTING_TIMEOUT_SECONDS,
) -> LangGraphResolveQuery:
    """Module-level helper to compose the selector with explicit defaults."""
    return LangGraphResolveQuery(
        classifier=classifier,
        answer_question=answer_question,
        analyze_claim=analyze_claim,
        trace_id_factory=trace_id_factory,
        callback_factory=callback_factory,
        timeout_seconds=timeout_seconds,
    )
