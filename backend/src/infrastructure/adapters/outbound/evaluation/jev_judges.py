"""Context relevance and groundedness as typed-decision probabilities.

Complementan las métricas deterministas con dos medidas que hoy faltan:
*context precision* (¿los pasajes entregados al modelo sirven para la pregunta?)
y *groundedness* (¿lo que afirma cada bloque lo sostienen las páginas que cita?).

CALIBRACIÓN PENDIENTE: son juicios de un modelo, no verdad. Antes de citarlos en
la memoria como resultado hay que medir su acuerdo con etiquetas humanas sobre
una muestra (p. ej. 30 pares) y reportar ese acuerdo junto a las cifras.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from application.ports.outbound.decision_model import DecisionModel, NoulQuestion

RELEVANCE_THRESHOLD = 0.5


async def context_relevance(
    model: DecisionModel, *, question: str, passages: Sequence[str]
) -> list[float]:
    """Probability, per delivered passage, that it helps answer ``question``."""

    if not passages:
        return []
    keys = [f"p{index}" for index in range(1, len(passages) + 1)]
    state = {"question": question, "passages": dict(zip(keys, passages, strict=True))}
    questions = {
        key: NoulQuestion(
            instructions=(
                f"El pasaje `passages.{key}` contiene información necesaria o útil para "
                "responder a la pregunta `question`."
            )
        )
        for key in keys
    }
    result = await model.decide(state, questions)
    return [result.noul(key) for key in keys]


async def groundedness(model: DecisionModel, *, claim: str, passages: Mapping[str, str]) -> float:
    """Probability that ``claim`` is fully supported by the cited ``passages``."""

    result = await model.decide(
        {"claim": claim, "cited_passages": dict(passages)},
        {
            "supported": NoulQuestion(
                instructions=(
                    "La afirmación `claim` está plenamente respaldada por los pasajes de "
                    "`cited_passages`: no añade datos, cifras ni condiciones que esos "
                    "pasajes no contengan."
                ),
                true="Todo lo que afirma aparece en los pasajes o se deduce directamente de ellos.",
                false="Afirma algo que los pasajes no dicen, o los contradice.",
            )
        },
    )
    return result.noul("supported")


def precision_at_threshold(probabilities: Sequence[float]) -> float | None:
    if not probabilities:
        return None
    return sum(p >= RELEVANCE_THRESHOLD for p in probabilities) / len(probabilities)
