"""The router's timeout must contain the workflows it dispatches to.

The routing workflow wraps classification AND the full question or claim
execution in one ``asyncio.timeout``. Its budget was 20s while the question
workflow allows 45s and the claim workflow 30s, so an auto-mode request could
never use the time the inner workflow was entitled to: it failed with
"routing workflow timed out" before the answer came back. The user saw
"Error desconocido" in the interface and no answer at all.
"""

import asyncio

import pytest

from infrastructure.adapters.outbound.claim_workflow.langgraph_workflow import (
    LangGraphClaimWorkflow,
)
from infrastructure.adapters.outbound.query_workflow.langgraph_workflow import (
    DEFAULT_ROUTING_TIMEOUT_SECONDS,
)
from infrastructure.adapters.outbound.question_workflow.langgraph_workflow import (
    LangGraphQuestionWorkflow,
)


def _default(cls: type, name: str = "timeout_seconds") -> float:
    """Read a constructor's declared default timeout."""
    import inspect

    return inspect.signature(cls.__init__).parameters[name].default


def test_routing_budget_exceeds_the_question_workflow_budget() -> None:
    inner = _default(LangGraphQuestionWorkflow)
    assert DEFAULT_ROUTING_TIMEOUT_SECONDS > inner, (
        f"the router allows {DEFAULT_ROUTING_TIMEOUT_SECONDS}s but contains a "
        f"question workflow allowed {inner}s"
    )


def test_routing_budget_exceeds_the_claim_workflow_budget() -> None:
    inner = _default(LangGraphClaimWorkflow)
    assert DEFAULT_ROUTING_TIMEOUT_SECONDS > inner, (
        f"the router allows {DEFAULT_ROUTING_TIMEOUT_SECONDS}s but contains a "
        f"claim workflow allowed {inner}s"
    )


def test_routing_budget_leaves_room_for_the_classification_itself() -> None:
    """The router also spends time classifying before it dispatches."""
    slowest_inner = max(
        _default(LangGraphQuestionWorkflow),
        _default(LangGraphClaimWorkflow),
    )
    assert DEFAULT_ROUTING_TIMEOUT_SECONDS >= slowest_inner + 10.0


@pytest.mark.parametrize("budget", [0, -1])
def test_routing_rejects_a_nonpositive_budget(budget: float) -> None:
    from infrastructure.adapters.outbound.query_workflow.langgraph_workflow import (
        build_resolve_query_workflow,
    )

    with pytest.raises(ValueError, match="timeout"):
        build_resolve_query_workflow(
            classifier=object(),  # type: ignore[arg-type]
            answer_question=object(),  # type: ignore[arg-type]
            analyze_claim=object(),  # type: ignore[arg-type]
            timeout_seconds=budget,
        )


def test_asyncio_timeout_semantics_are_what_the_budget_assumes() -> None:
    """Guard the assumption: an outer timeout smaller than an inner one wins."""

    async def scenario() -> str:
        try:
            async with asyncio.timeout(0.02):
                async with asyncio.timeout(1.0):
                    await asyncio.sleep(0.5)
        except TimeoutError:
            return "outer-wins"
        return "completed"

    assert asyncio.run(scenario()) == "outer-wins"
