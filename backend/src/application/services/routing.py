"""Closed-enum dispatch service that delegates to existing answer/claim ports."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from application.models.claim import ClaimExecution
from application.models.query import QueryExecution, QueryInput
from application.ports.inbound.analyze_claim import AnalyzeClaim
from application.ports.inbound.answer_question import AnswerQuestion
from application.ports.outbound.query_classifier import QueryClassifier
from domain.models.claim import ClaimInput
from domain.models.routing import (
    ClarificationResult,
    RouteDecision,
    RouteExecution,
)


class RouteExecutionError(RuntimeError):
    """Wraps any technical failure produced by the chosen flow."""


_CLOSED_DECISIONS: frozenset[RouteDecision] = frozenset(
    {"question", "claim", "clarification_required"}
)

_DEFAULT_CLARIFICATION = "Necesito más información para enrutar tu consulta."


async def resolve_query(
    query: QueryInput,
    classifier: QueryClassifier,
    answer_question: AnswerQuestion,
    analyze_claim: AnalyzeClaim,
) -> RouteExecution:
    """Run the closed-enum dispatch exactly once per query."""

    classification = await classifier.classify(query)
    decision = classification.decision
    allowed = sorted(_CLOSED_DECISIONS)
    if decision not in _CLOSED_DECISIONS:
        raise RouteExecutionError(
            f"unsupported routing decision: {decision!r}; expected one of {allowed}"
        )

    try:
        if decision == "question":
            dispatch: (
                QueryExecution | ClaimExecution | ClarificationResult
            ) = await answer_question.execute(query)
            trace_id = dispatch.trace_id
        elif decision == "claim":
            dispatch = await analyze_claim.execute(
                ClaimInput(text=query.text, language=query.language, clarifications=())
            )
            trace_id = dispatch.trace_id
        else:
            message = classification.rationale or _DEFAULT_CLARIFICATION
            dispatch = ClarificationResult(message=message, missing_fields=())
            trace_id = str(uuid.uuid4())
    except RouteExecutionError:
        raise
    except Exception as error:
        raise RouteExecutionError(f"routing flow raised {type(error).__name__}") from error

    return RouteExecution(
        query=query,
        classification=classification,
        dispatch=dispatch,
        trace_id=trace_id,
    )


ResolveQueryFn = Callable[
    [QueryInput, QueryClassifier, AnswerQuestion, AnalyzeClaim],
    Awaitable[RouteExecution],
]
