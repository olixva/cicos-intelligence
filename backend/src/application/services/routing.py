"""Closed-enum dispatch service that delegates to existing answer/claim ports."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from application.models.claim import ClaimExecution
from application.models.query import QueryExecution, QueryInput
from application.ports.inbound.analyze_claim import AnalyzeClaim
from application.ports.inbound.answer_question import AnswerQuestion
from application.ports.outbound.query_classifier import QueryClassifier
from application.services.claim_heuristics import looks_like_claim_text
from domain.models.claim import ClaimInput
from domain.models.routing import (
    ClarificationResult,
    RouteClassification,
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

    # Override heurístico: si la decisión NO es "claim" pero el texto
    # tiene vocabulario claro de relato de siniestro, forzamos "claim".
    # El router barato (gpt-5.6-luna) puede confundir palabras
    # incidentales como "tiempo" o "hora" con preguntas sobre el clima.
    # Sin este cortafuegos, un alcance trasero se queda sin analizar
    # porque el router dice "clarification_required" y el handler
    # genérico responde "no puedo informar del tiempo".
    if decision != "claim" and looks_like_claim_text(query.text):
        decision = "claim"
        classification = RouteClassification(
            decision=decision,
            rationale=(
                "Heurística de override: el router clasificó "
                f"{classification.decision!r} pero el texto contiene "
                "vocabulario claro de relato de siniestro."
            ),
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
