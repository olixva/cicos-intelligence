"""Auto-router backed by a typed decision model (one closed ``choice`` question)."""

from __future__ import annotations

from typing import cast

from application.models.query import QueryInput
from application.ports.outbound.decision_model import ChoiceQuestion, DecisionModel
from domain.models.routing import RouteClassification, RouteDecision

_QUESTION = ChoiceQuestion(
    instructions="¿Qué debe hacer un asistente de tramitación con este mensaje?",
    criteria={
        "question": (
            "El usuario hace una pregunta sobre el contenido del manual de convenios "
            "CIDE/ASCIDE/CICOS: ámbito, procedimiento, definiciones o normas."
        ),
        "claim": (
            "El usuario describe un siniestro concreto de tráfico entre vehículos para que "
            "se analice la responsabilidad."
        ),
        "clarification_required": (
            "El mensaje no es una pregunta sobre el manual ni el relato de un siniestro, "
            "o es demasiado vago para decidirlo."
        ),
    },
)


class JevQueryClassifier:
    """Implements ``QueryClassifier`` with probabilities instead of generated text.

    Por debajo de ``min_confidence`` se pide aclaración en lugar de adivinar. El
    umbral estándar ``0.4`` se eligió tras comparar el golden; vuelve a validarlo
    si cambia el modelo o el conjunto de casos.
    """

    def __init__(self, model: DecisionModel, *, min_confidence: float = 0.4) -> None:
        if not 0 <= min_confidence <= 1:
            raise ValueError("min_confidence must be between 0 and 1")
        self._model = model
        self._min_confidence = min_confidence

    async def classify(self, query: QueryInput) -> RouteClassification:
        result = await self._model.decide({"user_message": query.text}, {"route": _QUESTION})
        answer = result.choice("route")
        if answer.confidence < self._min_confidence:
            decision: RouteDecision = "clarification_required"
        else:
            decision = cast(RouteDecision, answer.choice)
        return RouteClassification(
            decision=decision,
            provider="typesafe",
            model=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )
