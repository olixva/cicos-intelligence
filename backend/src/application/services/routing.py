"""Closed-enum dispatch service that delegates to existing answer/claim ports."""

from __future__ import annotations

import re
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

# Marcadores típicos de relato de siniestro. El router barato
# (gpt-5.6-luna) puede clasificar un relato de colisión como
# "question" o "clarification_required" cuando el texto incluye
# palabras incidentales (caso real: "no consigue detenerse a tiempo"
# → el modelo entiende "tiempo" como una pregunta meteorológica y
# clasifica como clarification_required). Esta heurística es el
# cortafuegos: si el texto tiene al menos DOS de estos marcadores,
# forzamos "claim" para que el análisis corra sobre el texto.
_CLAIM_TEXT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bveh[ií]culo\s+[a-z]\b", re.IGNORECASE),
    re.compile(r"\bveh[ií]culos?\s+[a-z]\s+y\s+[a-z]\b", re.IGNORECASE),
    re.compile(r"\bsiniestro\b", re.IGNORECASE),
    re.compile(r"\bcolisi[oó]n\b", re.IGNORECASE),
    re.compile(r"\bchoc[oóaáe]+\b", re.IGNORECASE),
    re.compile(r"\bD\.\s?A\.\s?A\.\b", re.IGNORECASE),
    re.compile(r"\bmaniobra\b", re.IGNORECASE),
    re.compile(r"\bsem[aá]foro\b", re.IGNORECASE),
    re.compile(r"\bculpable\b", re.IGNORECASE),
    re.compile(r"\bfren[oóaá]\b", re.IGNORECASE),
    re.compile(r"\btrasera?\b", re.IGNORECASE),
    re.compile(r"\bmatr[ií]cula\b", re.IGNORECASE),
    re.compile(r"\bparte\s+amistoso\b", re.IGNORECASE),
    re.compile(r"\balcance\b", re.IGNORECASE),
    re.compile(r"\bimpacto\b", re.IGNORECASE),
)

_CLAIM_TEXT_THRESHOLD = 2


def _looks_like_claim_text(text: str) -> bool:
    """True si el texto tiene al menos ``_CLAIM_TEXT_THRESHOLD`` marcadores
    de relato de siniestro. Sirve para detectar casos donde el router
    barato clasifica mal por palabras incidentales (``tiempo``,
    ``hora``, ``parte``, etc.) que aparecen en un contexto claramente
    de colisión entre vehículos."""
    return (
        sum(1 for pattern in _CLAIM_TEXT_PATTERNS if pattern.search(text))
        >= _CLAIM_TEXT_THRESHOLD
    )


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
    if decision != "claim" and _looks_like_claim_text(query.text):
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
