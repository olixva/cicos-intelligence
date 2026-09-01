"""Ragas evaluator adapters operate only over serialized experiment fields."""

import asyncio
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class _MetricResult:
    value: float


@dataclass
class _RecordingFactualScorer:
    received: list[tuple[str, str]]

    async def ascore(self, *, response: str, reference: str) -> _MetricResult:
        self.received.append((response, reference))
        return _MetricResult(value=0.75)


def test_factual_evaluator_scores_only_serialized_answer_text_and_reference() -> None:
    from infrastructure.adapters.outbound.evaluation.ragas_evaluators import (
        build_factual_evaluator,
    )

    scorer = _RecordingFactualScorer(received=[])
    evaluator = build_factual_evaluator(scorer)

    evaluation = asyncio.run(
        evaluator(
            input={"text": "INPUT_SENTINEL"},
            output={
                "answer_text": "La respuesta entregada.",
                "result": {"blocks": [{"text": "OUTPUT_SENTINEL"}]},
                "context": [{"raw_page": "CONTEXT_SENTINEL"}],
                "trace_id": "TRACE_SENTINEL",
            },
            expected_output={
                "reference": "La respuesta de referencia.",
                "decisions": "EXPECTED_SENTINEL",
            },
            metadata={"case_id": "METADATA_SENTINEL"},
        )
    )

    assert scorer.received == [
        ("La respuesta entregada.", "La respuesta de referencia.")
    ]
    assert evaluation.name == "factual_f1"
    assert evaluation.value == 0.75


def test_factual_evaluator_rejects_missing_serialized_fields_before_scoring() -> None:
    from infrastructure.adapters.outbound.evaluation.ragas_evaluators import (
        build_factual_evaluator,
    )

    scorer = _RecordingFactualScorer(received=[])
    evaluator = build_factual_evaluator(scorer)

    try:
        asyncio.run(evaluator(output={}, expected_output={"reference": "Referencia"}))
    except ValueError as error:
        assert str(error) == "evaluation output requires a nonempty answer_text"
    else:
        raise AssertionError("missing answer_text must not invoke Ragas")

    assert scorer.received == []
