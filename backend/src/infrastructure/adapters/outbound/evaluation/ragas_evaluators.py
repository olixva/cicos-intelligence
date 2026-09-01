"""Native Ragas evaluators for serialized Langfuse experiment outputs.

Ragas 0.4.3 exposes ``FactualCorrectness.ascore(response=, reference=)`` and
Langfuse 4.15.1 exposes ``Evaluation`` as the public experiment score type.
This adapter intentionally uses those public APIs; it does not depend on the
legacy Ragas metric imports or on Langfuse internal experiment models.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Protocol, cast

from langfuse import Evaluation
from ragas.llms import InstructorBaseRagasLLM
from ragas.metrics.collections import FactualCorrectness


class FactualScore(Protocol):
    """The public result shape returned by Ragas factual correctness metrics."""

    @property
    def value(self) -> float: ...


class FactualScorer(Protocol):
    """Minimal Ragas scoring boundary, allowing network-free evaluator tests."""

    def ascore(self, *, response: str, reference: str) -> Awaitable[FactualScore]: ...


def build_factual_scorer(judge_llm: InstructorBaseRagasLLM) -> FactualCorrectness:
    """Configure Ragas's native F1 metric with claim-level detail enabled."""

    return FactualCorrectness(
        llm=judge_llm,
        mode="f1",
        atomicity="high",
        coverage="high",
    )


def build_factual_evaluator(
    scorer: FactualScorer,
) -> Callable[..., Awaitable[Evaluation]]:
    """Build a Langfuse evaluator over only the delivered answer and reference."""

    async def factual_evaluator(
        *, output: object, expected_output: object, **_: object
    ) -> Evaluation:
        answer_text = _required_text(output, "answer_text", "evaluation output")
        reference = _required_text(expected_output, "reference", "expected output")
        score = await scorer.ascore(response=answer_text, reference=reference)
        return Evaluation(name="factual_f1", value=score.value)

    return factual_evaluator


def _required_text(raw: object, field: str, subject: str) -> str:
    if not isinstance(raw, Mapping):
        raise ValueError(f"{subject} must be an object")
    value = cast(Mapping[str, object], raw).get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{subject} requires a nonempty {field}")
    return value
