"""Golden references must never cross into the evaluated question use case."""

import asyncio
from dataclasses import dataclass
from typing import Any

from application.models.query import QueryExecution, QueryInput, QuestionAnswer


@dataclass
class _SpyAnswerQuestion:
    received: list[QueryInput]

    async def execute(self, query: QueryInput) -> QueryExecution:
        self.received.append(query)
        return QueryExecution(result=QuestionAnswer("insufficient_evidence", ()), context=())


class _DatasetItem:
    input: Any = {"text": "Pregunta del usuario", "language": "es"}
    expected_output: Any = {"reference": "REFERENCE_SENTINEL"}
    metadata: Any = {"case_id": "fixture-case"}


def test_experiment_task_selects_only_native_input_fields() -> None:
    from infrastructure.adapters.outbound.evaluation.langfuse_experiments import build_question_task

    spy = _SpyAnswerQuestion(received=[])
    payload = asyncio.run(build_question_task(spy)(item=_DatasetItem()))

    assert spy.received == [QueryInput("Pregunta del usuario", "es")]
    assert "REFERENCE_SENTINEL" not in str(spy.received)
    assert payload["answer_text"] == ""
    assert payload["context"] == []
