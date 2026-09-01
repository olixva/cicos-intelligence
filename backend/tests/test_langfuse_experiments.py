"""Native Langfuse experiment runner operates only on the injected dataset client.

The tests deliberately avoid monkeypatching module globals: every test injects
its own fake ``Langfuse`` client and replaces ``bootstrap.build_answer_question``
with a deterministic spy. This mirrors the production wiring in
``bootstrap.build_question_experiment_runner`` without booting OpenAI, Qdrant
or any network-backed adapter.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, cast

import pytest

from application.models.query import (
    AnswerBlock,
    QueryExecution,
    QueryInput,
    QuestionAnswer,
)


@dataclass
class _RecordingAnswerQuestion:
    received: list[QueryInput] = field(default_factory=list)

    async def execute(self, query: QueryInput) -> QueryExecution:
        self.received.append(query)
        return QueryExecution(
            result=QuestionAnswer(
                "answered", (AnswerBlock("Respuesta.", ("sha256:abc:page:5",)),)
            ),
            context=(),
            trace_id="trace-spy",
        )


@dataclass
class _DatasetClientSpy:
    """Captures the kwargs of ``run_experiment`` and returns a frozen result."""

    result: Any
    run_calls: list[dict[str, Any]] = field(default_factory=list)
    get_dataset_calls: list[str] = field(default_factory=list)
    invoked_task: Any = None
    invoked_item: Any = None

    def run_experiment(self, **kwargs: Any) -> Any:
        self.run_calls.append(kwargs)
        task = kwargs["task"]
        if self.invoked_item is None:
            raise AssertionError("invoked_item must be set before invoking run_experiment")
        asyncio.run(task(item=self.invoked_item))
        self.invoked_task = task
        return self.result


@dataclass
class _LangfuseSpy:
    client: _DatasetClientSpy

    def get_dataset(self, name: str) -> _DatasetClientSpy:
        self.client.get_dataset_calls.append(name)
        return self.client


_EXPERIMENT_RESULT_SENTINEL = object()


def _evaluator_sentinel(
    *,
    input: Any = None,
    output: Any = None,
    expected_output: Any = None,
    metadata: Any = None,
    **_: Any,
) -> Any:
    """An evaluator that must never be observed by the AnswerQuestion spy."""


def _reset_module_state() -> None:
    """Reset the lazy module-level handle so each test starts from a known state."""

    from infrastructure.adapters.outbound.evaluation import langfuse_experiments as mod

    mod.langfuse = None


def _build_fake_item(
    *, text: str = "Pregunta", language: str = "es"
) -> Any:
    """Build a fake ``DatasetItem`` shaped like the Langfuse SDK item."""

    item = type(
        "_FakeDatasetItem",
        (),
        {
            "input": {"text": text, "language": language},
            "expected_output": {"reference": "REFERENCE_SENTINEL"},
            "metadata": {"case_id": "fixture-case"},
        },
    )()
    return item


def _wire_runner(
    monkeypatch: pytest.MonkeyPatch,
    *,
    fake_item: Any,
    max_concurrency: str | None = None,
    dataset_result: Any = _EXPERIMENT_RESULT_SENTINEL,
) -> tuple[_DatasetClientSpy, _RecordingAnswerQuestion]:
    """Wire the fakes, run the experiment, and return the spies."""

    _reset_module_state()

    spy_port = _RecordingAnswerQuestion()
    import bootstrap

    # ``run_question_experiment`` lazy-imports ``bootstrap.build_answer_question``,
    # so patching the symbol on the bootstrap module is the canonical seam.
    monkeypatch.setattr(bootstrap, "build_answer_question", lambda profile: spy_port)

    if max_concurrency is None:
        monkeypatch.delenv("ALLIANZ_LANGFUSE_MAX_CONCURRENCY", raising=False)
    else:
        monkeypatch.setenv("ALLIANZ_LANGFUSE_MAX_CONCURRENCY", max_concurrency)

    dataset_spy = _DatasetClientSpy(result=dataset_result, invoked_item=fake_item)
    langfuse_spy = _LangfuseSpy(client=dataset_spy)

    from infrastructure.adapters.outbound.evaluation.langfuse_experiments import (
        run_question_experiment,
    )

    result = run_question_experiment(
        profile_name="structured",
        dataset_name="golden",
        dataset_version="v1",
        evaluators=[_evaluator_sentinel],
        langfuse_client=cast(Any, langfuse_spy),
    )

    assert result is dataset_result
    return dataset_spy, spy_port


def test_run_question_experiment_rejects_blank_dataset_name() -> None:
    _reset_module_state()
    from infrastructure.adapters.outbound.evaluation.langfuse_experiments import (
        run_question_experiment,
    )

    with pytest.raises(ValueError, match="dataset_name"):
        run_question_experiment(
            profile_name="structured",
            dataset_name="   ",
            dataset_version="v1",
            evaluators=[],
        )


def test_run_question_experiment_rejects_blank_dataset_version() -> None:
    _reset_module_state()
    from infrastructure.adapters.outbound.evaluation.langfuse_experiments import (
        run_question_experiment,
    )

    with pytest.raises(ValueError, match="dataset_version"):
        run_question_experiment(
            profile_name="structured",
            dataset_name="golden",
            dataset_version="",
            evaluators=[],
        )


def test_run_question_experiment_rejects_blank_profile_name() -> None:
    _reset_module_state()
    from infrastructure.adapters.outbound.evaluation.langfuse_experiments import (
        run_question_experiment,
    )

    with pytest.raises(ValueError, match="profile_name"):
        run_question_experiment(
            profile_name="\t",
            dataset_name="golden",
            dataset_version="v1",
            evaluators=[],
        )


def test_max_concurrency_defaults_to_four_and_rejects_unparseable_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from infrastructure.adapters.outbound.evaluation.langfuse_experiments import (
        _resolve_max_concurrency,
    )

    monkeypatch.delenv("ALLIANZ_LANGFUSE_MAX_CONCURRENCY", raising=False)
    assert _resolve_max_concurrency() == 4

    monkeypatch.setenv("ALLIANZ_LANGFUSE_MAX_CONCURRENCY", "8")
    assert _resolve_max_concurrency() == 8

    monkeypatch.setenv("ALLIANZ_LANGFUSE_MAX_CONCURRENCY", "")
    assert _resolve_max_concurrency() == 4

    monkeypatch.setenv("ALLIANZ_LANGFUSE_MAX_CONCURRENCY", "not-a-number")
    with pytest.raises(ValueError, match="ALLIANZ_LANGFUSE_MAX_CONCURRENCY"):
        _resolve_max_concurrency()

    monkeypatch.setenv("ALLIANZ_LANGFUSE_MAX_CONCURRENCY", "0")
    with pytest.raises(ValueError, match="ALLIANZ_LANGFUSE_MAX_CONCURRENCY"):
        _resolve_max_concurrency()

    monkeypatch.setenv("ALLIANZ_LANGFUSE_MAX_CONCURRENCY", "-1")
    with pytest.raises(ValueError, match="ALLIANZ_LANGFUSE_MAX_CONCURRENCY"):
        _resolve_max_concurrency()


def test_run_question_experiment_calls_dataset_client_run_experiment_once_with_keyword_kwargs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_item = _build_fake_item()
    dataset_spy, _ = _wire_runner(monkeypatch, fake_item=fake_item)

    assert dataset_spy.get_dataset_calls == ["golden"]
    assert len(dataset_spy.run_calls) == 1
    call = dataset_spy.run_calls[0]
    assert call["name"] == "golden"
    assert call["run_name"] == "structured-v1"
    assert callable(call["task"])
    assert call["evaluators"][0] is _evaluator_sentinel
    assert call["max_concurrency"] == 4


def test_run_question_experiment_respects_max_concurrency_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_item = _build_fake_item()
    dataset_spy, _ = _wire_runner(monkeypatch, fake_item=fake_item, max_concurrency="12")

    assert dataset_spy.run_calls[0]["max_concurrency"] == 12


def test_run_question_experiment_never_lets_expected_output_reach_query_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dataset item carrying a sentinel reference must not leak into the workflow port."""

    fake_item = _build_fake_item()
    _, spy_port = _wire_runner(monkeypatch, fake_item=fake_item)

    assert spy_port.received == [QueryInput("Pregunta", "es")]
    serialized = " ".join(repr(item) for item in spy_port.received)
    assert "REFERENCE_SENTINEL" not in serialized
    assert "fixture-case" not in serialized


def test_run_question_experiment_returns_the_sdk_experiment_result_untouched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The runner must not wrap, reshape or filter the SDK return value."""

    class _CustomResult:
        marker = "I am the SDK result"

    fake_item = _build_fake_item()
    dataset_spy, _ = _wire_runner(
        monkeypatch,
        fake_item=fake_item,
        dataset_result=_CustomResult(),
    )

    assert dataset_spy.result.marker == "I am the SDK result"
    assert len(dataset_spy.run_calls) == 1
