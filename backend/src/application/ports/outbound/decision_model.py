"""Outbound contract for typed decisions: probabilities over closed questions.

Un modelo de decisión no genera texto: responde preguntas tipadas sobre un
estado (probabilidad de sí, elección entre opciones cerradas). Por eso una
inyección en el estado sólo puede desplazar probabilidades, nunca emitir
contenido libre. Los fallos técnicos reutilizan la jerarquía de
``LanguageModelError`` para que la API los traduzca igual que los del LLM.
"""

from collections.abc import Awaitable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from application.ports.outbound.language_model import LanguageModelError

__all__ = [
    "Answer",
    "ChoiceAnswer",
    "ChoiceQuestion",
    "DecisionModel",
    "DecisionResult",
    "NoulAnswer",
    "NoulQuestion",
    "Question",
]


@dataclass(frozen=True, slots=True)
class NoulQuestion:
    """A yes/no condition; the answer is the probability that it holds."""

    instructions: str
    true: str | None = None
    false: str | None = None

    def __post_init__(self) -> None:
        if not self.instructions.strip():
            raise ValueError("noul question instructions must be nonempty")


@dataclass(frozen=True, slots=True)
class ChoiceQuestion:
    """Select exactly one of the closed options described in ``criteria``."""

    instructions: str
    criteria: Mapping[str, str]

    def __post_init__(self) -> None:
        if not self.instructions.strip():
            raise ValueError("choice question instructions must be nonempty")
        if len(self.criteria) < 2:
            raise ValueError("choice question needs at least two options")


type Question = NoulQuestion | ChoiceQuestion


@dataclass(frozen=True, slots=True)
class NoulAnswer:
    probability: float


@dataclass(frozen=True, slots=True)
class ChoiceAnswer:
    choice: str
    confidence: float
    probabilities: Mapping[str, float]


type Answer = NoulAnswer | ChoiceAnswer


@dataclass(frozen=True, slots=True)
class DecisionResult:
    """Answers keyed by question name, plus provider accounting."""

    answers: Mapping[str, Answer]
    model: str
    input_tokens: int
    output_tokens: int

    def noul(self, name: str) -> float:
        answer = self.answers[name]
        if not isinstance(answer, NoulAnswer):
            raise LanguageModelError(f"answer {name!r} is not a noul answer")
        return answer.probability

    def choice(self, name: str) -> ChoiceAnswer:
        answer = self.answers[name]
        if not isinstance(answer, ChoiceAnswer):
            raise LanguageModelError(f"answer {name!r} is not a choice answer")
        return answer


class DecisionModel(Protocol):
    """Answer every question in one parallel call about the same state."""

    def decide(
        self, state: str | Mapping[str, Any], questions: Mapping[str, Question]
    ) -> Awaitable[DecisionResult]: ...
