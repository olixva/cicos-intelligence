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
    umbral por defecto NO está calibrado: ajústalo con el golden (modo ``auto``).
    """

    def __init__(self, model: DecisionModel, *, min_confidence: float = 0.6) -> None:
        if not 0 <= min_confidence <= 1:
            raise ValueError("min_confidence must be between 0 and 1")
        self._model = model
        self._min_confidence = min_confidence

    async def classify(self, query: QueryInput) -> RouteClassification:
        result = await self._model.decide({"user_message": query.text}, {"route": _QUESTION})
        answer = result.choice("route")
        if answer.confidence < self._min_confidence:
            return RouteClassification(decision="clarification_required")
        return RouteClassification(decision=cast(RouteDecision, answer.choice))
