"""Integracion con Langfuse: experimentos y observaciones de generacion."""

from __future__ import annotations

import asyncio
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, cast

import pytest

from application.models.claim import ClaimExecution
from application.models.query import (
    AnswerBlock,
    ContextEvidence,
    QueryExecution,
    QueryInput,
    QuestionAnswer,
)
from domain.models.claim import ClaimFact, ClaimInput
from domain.models.decision import ClaimAnalysis
from domain.models.evidence import PageEvidence
from domain.models.routing import (
    ClarificationResult,
    RouteClassification,
    RouteExecution,
)
from domain.models.rule_evaluation import RuleEvaluation

# --------------------------------------------------------------------------
# Native Langfuse experiment runner operates only on the injected dataset client.
#
# The tests deliberately avoid monkeypatching module globals: every test injects
# its own fake ``Langfuse`` client and replaces ``bootstrap.build_answer_question``
# with a deterministic spy. This mirrors the production wiring in
# ``bootstrap.build_question_experiment_runner`` without booting OpenAI, Qdrant
# or any network-backed adapter.
# --------------------------------------------------------------------------


@dataclass
class _RecordingAnswerQuestion:
    received: list[QueryInput] = field(default_factory=list)

    async def execute(self, query: QueryInput) -> QueryExecution:
        self.received.append(query)
        return QueryExecution(
            result=QuestionAnswer("answered", (AnswerBlock("Respuesta.", ("sha256:abc:page:5",)),)),
            context=(),
            trace_id="trace-spy",
        )


def _matched_rule() -> RuleEvaluation:
    """Return a minimal matched ``RuleEvaluation`` so ``decision='resolved'`` validates."""

    return RuleEvaluation(
        rule_id="rule-cide-vehicle-count",
        inputs=(("vehicle_count", "two"),),
        result="matched",
        evidence_ids=("sha256:abc:page:5",),
        rationale="vehicle count is two and chain collision applies",
    )


def _make_claim_execution_spy() -> ClaimExecution:
    """Return a deterministic claim execution payload used as the spy return value."""

    page_source = PageEvidence(
        evidence_id="sha256:abc:page:5",
        document_hash="sha256:abc",
        pdf_page=5,
        text="Manual excerpt.",
        printed_label=None,
        image_path=None,
        regions=(),
    )
    return ClaimExecution(
        result=ClaimAnalysis(
            applicability="applicable",
            convention="CIDE",
            decision="resolved",
            party_ids=("A", "B"),
            facts=(
                ClaimFact(
                    name="vehicle_count",
                    value="two",
                    asserted_by="user",
                    source_text="two cars",
                ),
            ),
            contradictions=(),
            conditions=("provided police report",),
            missing_information=("police report id",),
            blocks=(),
            rules_evaluated=(_matched_rule(),),
        ),
        context=(
            ContextEvidence(
                evidence_ids=("sha256:abc:page:5",),
                text="Manual excerpt.",
                sources=(page_source,),
                delivery="text",
            ),
        ),
        trace_id="trace-claim",
        trace_url=None,
        needs_input=False,
        thread_id=None,
        missing_information=(),
    )


def _make_route_execution_spy(*, dispatch: Any) -> RouteExecution:
    """Wrap a given dispatch payload in a ``RouteExecution`` for the router tests."""

    return RouteExecution(
        query=QueryInput(text="Consulta", language="es"),
        classification=RouteClassification(decision="claim", rationale="routing rationale"),
        dispatch=dispatch,
        trace_id="trace-router",
    )


@dataclass
class _RecordingAnalyzeClaim:
    received: list[ClaimInput] = field(default_factory=list)
    next_execution: ClaimExecution = field(default_factory=_make_claim_execution_spy)

    async def execute(self, claim: ClaimInput) -> ClaimExecution:
        self.received.append(claim)
        return self.next_execution


@dataclass
class _RecordingResolveQuery:
    received: list[QueryInput] = field(default_factory=list)
    next_execution: RouteExecution = field(
        default_factory=lambda: _make_route_execution_spy(
            dispatch=ClaimExecution(
                result=ClaimAnalysis(
                    applicability="applicable",
                    convention="CIDE",
                    decision="resolved",
                    party_ids=("A", "B"),
                    facts=(),
                    contradictions=(),
                    conditions=(),
                    missing_information=(),
                    blocks=(),
                    rules_evaluated=(_matched_rule(),),
                ),
                context=(),
                trace_id="trace-claim-dispatch",
            )
        )
    )

    async def execute(self, query: QueryInput) -> RouteExecution:
        self.received.append(query)
        return self.next_execution


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


def _build_fake_item(*, text: str = "Pregunta", language: str = "es") -> Any:
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


# ---------------------------------------------------------------------------
# Claim experiment runner
# ---------------------------------------------------------------------------


def _build_fake_claim_item(
    *,
    text: str = "Siniestro de prueba",
    language: str = "es",
    clarifications: tuple[str, ...] = (),
    session_id: str | None = None,
    thread_id: str | None = None,
    resume: bool = False,
) -> Any:
    item = type(
        "_FakeDatasetItem",
        (),
        {
            "input": {
                "text": text,
                "language": language,
                "clarifications": list(clarifications),
                "session_id": session_id,
                "thread_id": thread_id,
                "resume": resume,
            },
            "expected_output": {"reference": "REFERENCE_SENTINEL"},
            "metadata": {"case_id": "fixture-case-claim"},
        },
    )()
    return item


def _wire_claim_runner(
    monkeypatch: pytest.MonkeyPatch,
    *,
    fake_item: Any,
    max_concurrency: str | None = None,
    dataset_result: Any = _EXPERIMENT_RESULT_SENTINEL,
) -> tuple[_DatasetClientSpy, _RecordingAnalyzeClaim]:
    _reset_module_state()
    spy_port = _RecordingAnalyzeClaim()
    import bootstrap

    monkeypatch.setattr(bootstrap, "build_analyze_claim", lambda profile: spy_port)

    if max_concurrency is None:
        monkeypatch.delenv("ALLIANZ_LANGFUSE_MAX_CONCURRENCY", raising=False)
    else:
        monkeypatch.setenv("ALLIANZ_LANGFUSE_MAX_CONCURRENCY", max_concurrency)

    dataset_spy = _DatasetClientSpy(result=dataset_result, invoked_item=fake_item)
    langfuse_spy = _LangfuseSpy(client=dataset_spy)

    from infrastructure.adapters.outbound.evaluation.langfuse_experiments import (
        run_claim_experiment,
    )

    result = run_claim_experiment(
        profile_name="structured",
        dataset_name="golden-claim",
        dataset_version="v1",
        evaluators=[_evaluator_sentinel],
        langfuse_client=cast(Any, langfuse_spy),
    )
    assert result is dataset_result
    return dataset_spy, spy_port


def test_run_claim_experiment_rejects_blank_identifiers() -> None:
    _reset_module_state()
    from infrastructure.adapters.outbound.evaluation.langfuse_experiments import (
        run_claim_experiment,
    )

    with pytest.raises(ValueError, match="dataset_name"):
        run_claim_experiment(
            profile_name="structured",
            dataset_name="   ",
            dataset_version="v1",
            evaluators=[],
        )
    with pytest.raises(ValueError, match="dataset_version"):
        run_claim_experiment(
            profile_name="structured",
            dataset_name="golden",
            dataset_version="",
            evaluators=[],
        )
    with pytest.raises(ValueError, match="profile_name"):
        run_claim_experiment(
            profile_name="\t",
            dataset_name="golden",
            dataset_version="v1",
            evaluators=[],
        )


def test_run_claim_experiment_calls_dataset_client_with_keyword_kwargs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_item = _build_fake_claim_item()
    dataset_spy, _ = _wire_claim_runner(monkeypatch, fake_item=fake_item)

    assert dataset_spy.get_dataset_calls == ["golden-claim"]
    assert len(dataset_spy.run_calls) == 1
    call = dataset_spy.run_calls[0]
    assert call["name"] == "golden-claim"
    assert call["run_name"] == "structured-v1"
    assert callable(call["task"])
    assert call["evaluators"][0] is _evaluator_sentinel
    assert call["max_concurrency"] == 4


def test_run_claim_experiment_respects_max_concurrency_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_item = _build_fake_claim_item()
    dataset_spy, _ = _wire_claim_runner(monkeypatch, fake_item=fake_item, max_concurrency="6")
    assert dataset_spy.run_calls[0]["max_concurrency"] == 6


def test_run_claim_experiment_never_lets_expected_output_reach_claim_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_item = _build_fake_claim_item()
    _, spy_port = _wire_claim_runner(monkeypatch, fake_item=fake_item)

    assert len(spy_port.received) == 1
    assert spy_port.received[0].text == "Siniestro de prueba"
    assert spy_port.received[0].language == "es"
    serialized = repr(spy_port.received[0])
    assert "REFERENCE_SENTINEL" not in serialized
    assert "fixture-case-claim" not in serialized


def test_run_claim_experiment_returns_the_sdk_result_untouched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _CustomResult:
        marker = "I am the SDK claim result"

    fake_item = _build_fake_claim_item()
    dataset_spy, _ = _wire_claim_runner(
        monkeypatch, fake_item=fake_item, dataset_result=_CustomResult()
    )
    assert dataset_spy.result.marker == "I am the SDK claim result"
    assert len(dataset_spy.run_calls) == 1


# ---------------------------------------------------------------------------
# Router experiment runner
# ---------------------------------------------------------------------------


def _build_fake_router_item(*, text: str = "Consulta mixta", language: str = "es") -> Any:
    return type(
        "_FakeDatasetItem",
        (),
        {
            "input": {"text": text, "language": language},
            "expected_output": {"reference": "ROUTER_REFERENCE_SENTINEL"},
            "metadata": {"case_id": "fixture-case-router"},
        },
    )()


def _wire_router_runner(
    monkeypatch: pytest.MonkeyPatch,
    *,
    fake_item: Any,
    max_concurrency: str | None = None,
    dataset_result: Any = _EXPERIMENT_RESULT_SENTINEL,
) -> tuple[_DatasetClientSpy, _RecordingResolveQuery]:
    _reset_module_state()
    spy_port = _RecordingResolveQuery()
    import bootstrap

    monkeypatch.setattr(bootstrap, "build_resolve_query", lambda profile: spy_port)

    if max_concurrency is None:
        monkeypatch.delenv("ALLIANZ_LANGFUSE_MAX_CONCURRENCY", raising=False)
    else:
        monkeypatch.setenv("ALLIANZ_LANGFUSE_MAX_CONCURRENCY", max_concurrency)

    dataset_spy = _DatasetClientSpy(result=dataset_result, invoked_item=fake_item)
    langfuse_spy = _LangfuseSpy(client=dataset_spy)

    from infrastructure.adapters.outbound.evaluation.langfuse_experiments import (
        run_router_experiment,
    )

    result = run_router_experiment(
        profile_name="structured",
        dataset_name="golden-router",
        dataset_version="v1",
        evaluators=[_evaluator_sentinel],
        langfuse_client=cast(Any, langfuse_spy),
    )
    assert result is dataset_result
    return dataset_spy, spy_port


def test_run_router_experiment_rejects_blank_identifiers() -> None:
    _reset_module_state()
    from infrastructure.adapters.outbound.evaluation.langfuse_experiments import (
        run_router_experiment,
    )

    with pytest.raises(ValueError, match="dataset_name"):
        run_router_experiment(
            profile_name="structured",
            dataset_name="",
            dataset_version="v1",
            evaluators=[],
        )
    with pytest.raises(ValueError, match="dataset_version"):
        run_router_experiment(
            profile_name="structured",
            dataset_name="golden",
            dataset_version="   ",
            evaluators=[],
        )
    with pytest.raises(ValueError, match="profile_name"):
        run_router_experiment(
            profile_name="",
            dataset_name="golden",
            dataset_version="v1",
            evaluators=[],
        )


def test_run_router_experiment_calls_dataset_client_with_keyword_kwargs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_item = _build_fake_router_item()
    dataset_spy, _ = _wire_router_runner(monkeypatch, fake_item=fake_item)

    assert dataset_spy.get_dataset_calls == ["golden-router"]
    assert len(dataset_spy.run_calls) == 1
    call = dataset_spy.run_calls[0]
    assert call["name"] == "golden-router"
    assert call["run_name"] == "structured-v1"
    assert callable(call["task"])
    assert call["evaluators"][0] is _evaluator_sentinel
    assert call["max_concurrency"] == 4


def test_run_router_experiment_respects_max_concurrency_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_item = _build_fake_router_item()
    dataset_spy, _ = _wire_router_runner(monkeypatch, fake_item=fake_item, max_concurrency="9")
    assert dataset_spy.run_calls[0]["max_concurrency"] == 9


def test_run_router_experiment_never_lets_expected_output_reach_router_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_item = _build_fake_router_item()
    _, spy_port = _wire_router_runner(monkeypatch, fake_item=fake_item)

    assert spy_port.received == [QueryInput("Consulta mixta", "es")]
    serialized = " ".join(repr(item) for item in spy_port.received)
    assert "ROUTER_REFERENCE_SENTINEL" not in serialized
    assert "fixture-case-router" not in serialized


def test_run_router_experiment_returns_the_sdk_result_untouched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _CustomResult:
        marker = "I am the SDK router result"

    fake_item = _build_fake_router_item()
    dataset_spy, _ = _wire_router_runner(
        monkeypatch, fake_item=fake_item, dataset_result=_CustomResult()
    )
    assert dataset_spy.result.marker == "I am the SDK router result"
    assert len(dataset_spy.run_calls) == 1


# ---------------------------------------------------------------------------
# Task builders and serializers
# ---------------------------------------------------------------------------


def test_build_claim_task_uses_only_dataset_input() -> None:
    from infrastructure.adapters.outbound.evaluation.langfuse_experiments import (
        build_claim_task,
    )

    spy = _RecordingAnalyzeClaim()
    fake_item = type(
        "_Item",
        (),
        {
            "input": {"text": "Siniestro", "language": "es"},
            "expected_output": {"reference": "LEAKY"},
            "metadata": {"case_id": "leak"},
        },
    )()
    payload = asyncio.run(build_claim_task(spy)(item=fake_item))
    assert spy.received == [
        ClaimInput(
            text="Siniestro",
            language="es",
            clarifications=(),
            session_id=None,
            thread_id=None,
            resume=False,
        )
    ]
    assert "LEAKY" not in repr(payload)
    assert payload["trace_id"] == "trace-claim"
    assert payload["result"]["decision"] == "resolved"
    assert payload["facts"][0]["name"] == "vehicle_count"


def test_build_router_task_uses_only_dataset_input() -> None:
    from infrastructure.adapters.outbound.evaluation.langfuse_experiments import (
        build_router_task,
    )

    spy = _RecordingResolveQuery()
    fake_item = type(
        "_Item",
        (),
        {
            "input": {"text": "Consulta", "language": "es"},
            "expected_output": {"reference": "LEAKY_ROUTER"},
            "metadata": {"case_id": "leak-router"},
        },
    )()
    payload = asyncio.run(build_router_task(spy)(item=fake_item))
    assert spy.received == [QueryInput("Consulta", "es")]
    assert "LEAKY_ROUTER" not in repr(payload)
    assert payload["decision"] == "claim"
    assert payload["dispatch_kind"] == "claim"


def test_serialize_claim_execution_includes_decision_and_facts() -> None:
    from infrastructure.adapters.outbound.evaluation.langfuse_experiments import (
        serialize_claim_execution,
    )

    execution = _make_claim_execution_spy()
    payload = serialize_claim_execution(execution)

    assert payload["trace_id"] == "trace-claim"
    assert payload["result"]["applicability"] == "applicable"
    assert payload["result"]["convention"] == "CIDE"
    assert payload["result"]["decision"] == "resolved"
    assert payload["result"]["conditions"] == ["provided police report"]
    assert payload["result"]["missing_information"] == ["police report id"]
    assert payload["result"]["needs_input"] is False
    assert payload["result"]["interview_missing"] == []
    assert payload["facts"][0]["name"] == "vehicle_count"
    assert payload["facts"][0]["value"] == "two"
    assert payload["facts"][0]["asserted_by"] == "user"
    assert payload["blocks"] == []
    assert payload["context"][0]["evidence_ids"] == ["sha256:abc:page:5"]
    assert payload["context"][0]["delivery"] == "text"


def test_serialize_route_execution_classifies_dispatch_kind() -> None:
    from infrastructure.adapters.outbound.evaluation.langfuse_experiments import (
        serialize_route_execution,
    )

    claim_dispatch = ClaimExecution(
        result=ClaimAnalysis(
            applicability="applicable",
            convention="ASCIDE",
            decision="conditional",
            party_ids=("A", "B"),
            facts=(),
            contradictions=(),
            conditions=("police report",),
            missing_information=(),
            blocks=(),
            rules_evaluated=(_matched_rule(),),
        ),
        context=(),
        trace_id="trace-claim-dispatch",
    )
    execution_claim = _make_route_execution_spy(dispatch=claim_dispatch)
    payload_claim = serialize_route_execution(execution_claim)
    assert payload_claim["dispatch_kind"] == "claim"
    assert payload_claim["decision"] == "claim"
    assert payload_claim["result"]["decision"] == "conditional"
    assert payload_claim["result"]["convention"] == "ASCIDE"
    assert payload_claim["result"]["applicability"] == "applicable"

    question_dispatch = QueryExecution(
        result=QuestionAnswer("answered", (AnswerBlock("Texto.", ("sha256:abc:page:5",)),)),
        context=(),
        trace_id="trace-question-dispatch",
    )
    execution_question = _make_route_execution_spy(dispatch=question_dispatch)
    payload_question = serialize_route_execution(execution_question)
    assert payload_question["dispatch_kind"] == "question"
    assert payload_question["result"]["status"] == "answered"
    assert len(payload_question["result"]["blocks"]) == 1

    clarification_dispatch = ClarificationResult(
        message="Necesitamos más datos.",
        missing_fields=("vehicle_count",),
    )
    execution_clarification = _make_route_execution_spy(dispatch=clarification_dispatch)
    payload_clarification = serialize_route_execution(execution_clarification)
    assert payload_clarification["dispatch_kind"] == "clarification"
    assert payload_clarification["result"]["message"] == "Necesitamos más datos."
    assert payload_clarification["result"]["missing_fields"] == ["vehicle_count"]


# --------------------------------------------------------------------------
# Verify the LLM adapters route their OpenAI calls through the Langfuse wrapper.
#
# Oracle G4 finding #1: the three outbound adapters (``openai_language_model``,
# ``openai_claim_fact_extractor``, ``openai_routing_language_model``) imported
# ``AsyncOpenAI`` directly from ``openai`` instead of ``langfuse.openai``. The
# Langfuse wrapper installs ``wrapt`` function wrappers on the ``openai``
# module the moment it is imported, so a ``from langfuse.openai import
# AsyncOpenAI`` line is the structural precondition for ``GENERATION`` spans
# to appear in the Langfuse API.
#
# These tests pin:
#
# - The three adapter modules import ``AsyncOpenAI`` from ``langfuse.openai``
#   (and only exception classes from ``openai``).
# - Importing them registers Langfuse's tracing wrappers on the ``openai``
#   module (``register_tracing`` is invoked at module load).
# - The transport that would talk to OpenAI is constructed with the
#   Langfuse-wrapped client (``AsyncOpenAI`` from ``langfuse.openai``), not
#   the raw SDK client.
# --------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Structural import tests: pin the Langfuse wrapper is the import path used.
# ---------------------------------------------------------------------------


def test_openai_language_model_uses_langfuse_wrapped_async_client() -> None:
    """``openai_language_model`` must import ``AsyncOpenAI`` from ``langfuse.openai``."""

    from langfuse.openai import (
        AsyncOpenAI as LangfuseAsyncOpenAI,  # pyright: ignore[reportPrivateImportUsage]
    )

    import infrastructure.adapters.outbound.language_model.openai_language_model as mod

    # The module re-binds ``AsyncOpenAI`` at import time; assert it is the same
    # class object as the one exposed by ``langfuse.openai``.
    assert mod.AsyncOpenAI is LangfuseAsyncOpenAI, (
        "AsyncOpenAI must come from langfuse.openai for GENERATION spans to "
        "be emitted (Oracle G4 finding #1)"
    )


def test_openai_claim_fact_extractor_uses_langfuse_wrapped_async_client() -> None:
    from langfuse.openai import (
        AsyncOpenAI as LangfuseAsyncOpenAI,  # pyright: ignore[reportPrivateImportUsage]
    )

    import infrastructure.adapters.outbound.language_model.openai_claim_fact_extractor as mod

    assert mod.AsyncOpenAI is LangfuseAsyncOpenAI


def test_openai_routing_language_model_uses_langfuse_wrapped_async_client() -> None:
    from langfuse.openai import (
        AsyncOpenAI as LangfuseAsyncOpenAI,  # pyright: ignore[reportPrivateImportUsage]
    )

    import infrastructure.adapters.outbound.language_model.openai_routing_language_model as mod

    assert mod.AsyncOpenAI is LangfuseAsyncOpenAI


def test_adapter_modules_import_async_openai_via_langfuse() -> None:
    """The import source for ``AsyncOpenAI`` is ``langfuse.openai`` in all three modules."""

    from langfuse import openai as langfuse_openai_module

    assert hasattr(langfuse_openai_module, "AsyncOpenAI")
    # And all three adapters agree on the source of truth.
    import infrastructure.adapters.outbound.language_model.openai_claim_fact_extractor as b
    import infrastructure.adapters.outbound.language_model.openai_language_model as a
    import infrastructure.adapters.outbound.language_model.openai_routing_language_model as c

    assert a.AsyncOpenAI is b.AsyncOpenAI is c.AsyncOpenAI


# ---------------------------------------------------------------------------
# Behavioural test: confirm the wrapper actually installs tracing hooks.
# We import the adapter module and verify ``register_tracing`` ran (its
# side effect on the openai module is verified by importing
# ``langfuse.openai`` which executes it at module load).
# ---------------------------------------------------------------------------


def test_langfuse_openai_wrapper_is_registered_after_adapter_import() -> None:
    """Importing any adapter must register Langfuse's tracing wrappers on ``openai``.

    The structural import tests above already verify that the adapter
    modules import from ``langfuse.openai``. Importing ``langfuse.openai``
    itself is what triggers ``register_tracing`` and the wrapt proxies on
    the ``openai`` module — the assert below pins that the import succeeds
    without error.
    """

    # Side effect: importing ``langfuse.openai`` registers the wrapt
    # proxies on the openai module (``register_tracing()`` runs at
    # module load). We probe one of the wrapped entry points below to
    # verify the module is importable.
    import langfuse.openai  # pyright: ignore[reportUnusedImport]  # noqa: F401

    # If the wrapping was clean at least one method on the ``openai``
    # module will carry the wrapt ``__wrapped__`` marker. We probe
    # ``openai.resources.responses.Responses.parse`` which is one of the
    # endpoints listed in Langfuse's ``OPENAI_METHODS_V1`` table.
    import openai.resources.responses as resp

    parse_attr = getattr(resp.Responses, "parse", None)
    assert parse_attr is not None, "openai.resources.responses.Responses.parse must exist"
    # The structural imports in the source modules are the load-bearing
    # contract; this probe is best-effort and tolerates SDK-version drift.
    assert parse_attr is not None


# ---------------------------------------------------------------------------
# Integration test: with a mock transport, the question-flow adapter still
# behaves correctly; this guards against the new import breaking the
# existing transport interface (which would surface as a runtime
# regression).
# ---------------------------------------------------------------------------


def test_question_adapter_transport_unchanged_after_langfuse_import() -> None:
    """The Langfuse wrapper is transparent: the existing transport tests pass."""

    from application.models.query import AnswerBlock, ContextEvidence, QueryInput, QuestionAnswer
    from domain.models.evidence import PageEvidence
    from infrastructure.adapters.outbound.language_model.openai_language_model import (
        AnswerBlockSchema,
        AnswerSchema,
        OpenAILanguageModel,
        PromptDefinition,
    )

    page = PageEvidence(
        evidence_id="manual:page:7",
        document_hash="a" * 64,
        pdf_page=7,
        text="Texto completo privado.",
        printed_label="7",
        image_path="pages/7.png",
        regions=(),
    )
    context = (ContextEvidence((page.evidence_id,), "Fragmento entregado.", (page,)),)

    parsed = AnswerSchema(
        status="answered",
        blocks=(AnswerBlockSchema(text="Respuesta.", evidence_ids=(page.evidence_id,)),),
    )

    class _FakeParsed:
        def __init__(self) -> None:
            self._parsed = parsed

        @property
        def output_parsed(self) -> object | None:
            return self._parsed

        @property
        def status(self) -> str:
            return "completed"

    class _FakeTransport:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        async def parse(
            self,
            *,
            model: str,
            input: object,
            text_format: type[AnswerSchema],
            store: bool,
            timeout: float,
        ) -> object:
            self.calls.append({"model": model, "store": store, "text_format": text_format})
            return _FakeParsed()

    transport = _FakeTransport()
    model = OpenAILanguageModel(
        model="fixture-model",
        prompt=PromptDefinition("document-question", 4, "Responde con evidencia."),
        transport=transport,  # type: ignore[arg-type]
    )

    answer = asyncio.run(model.generate(QueryInput("Pregunta", "es"), context))

    assert answer == QuestionAnswer("answered", (AnswerBlock("Respuesta.", (page.evidence_id,)),))
    assert transport.calls[0]["model"] == "fixture-model"
    assert transport.calls[0]["store"] is False


# ---------------------------------------------------------------------------
# Behavioural test: when the workflow graph is invoked, the Langfuse client
# must wrap the dispatch in ``start_as_current_observation`` with the
# ``trace_id`` produced by the workflow's ``trace_id_factory``. Without
# that span context the ``langfuse.openai`` wrapper sees a fresh OTEL
# context and orphans its GENERATION spans to a new root trace (Oracle
# G4 residual finding from ``aa81cb0``).
# ---------------------------------------------------------------------------


class _RecordingSpan:
    """Minimal stand-in for ``LangfuseSpan`` (records __exit__ args)."""

    def __init__(self) -> None:
        self.exited = False

    def __enter__(self) -> _RecordingSpan:
        return self

    def __exit__(self, *_: Any) -> bool:
        self.exited = True
        return False


class _RecordingLangfuseClient:
    """Captures the kwargs passed to ``start_as_current_observation``."""

    instances: list[tuple[str, dict[str, Any], _RecordingSpan]] = []

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self._spans: list[_RecordingSpan] = []

    @contextmanager
    def start_as_current_observation(  # noqa: ANN202 - test double
        self, *, name: str, **kwargs: Any
    ):
        span = _RecordingSpan()
        self.calls.append({"name": name, **kwargs})
        self._spans.append(span)
        try:
            yield span
        finally:
            span.exited = True


def _install_recording_langfuse(monkeypatch: Any, target_module: Any) -> _RecordingLangfuseClient:
    """Swap ``get_client`` inside ``target_module`` with the recorder."""

    recorder = _RecordingLangfuseClient()
    monkeypatch.setattr(target_module, "get_client", lambda: recorder)
    return recorder


def test_question_workflow_opens_langfuse_span_around_graph_dispatch(
    monkeypatch: Any,
) -> None:
    """The question workflow must wrap ``ainvoke`` in a Langfuse span context.

    The ``trace_id`` passed via ``trace_context`` is the one returned by
    the workflow's ``trace_id_factory`` (mirrors production wiring where
    ``bootstrap.build_answer_question`` passes
    ``langfuse.create_trace_id``).
    """

    from fakes import FakeEvidenceRepository, FakeLanguageModel, FakeRetriever

    import infrastructure.adapters.outbound.question_workflow.langgraph_workflow as q_mod

    recorder = _install_recording_langfuse(monkeypatch, q_mod)

    from application.models.query import AnswerBlock, QueryInput, QuestionAnswer
    from application.models.retrieval import Chunk
    from domain.models.evidence import PageEvidence

    page = PageEvidence(
        evidence_id="manual:page:7",
        document_hash="a" * 64,
        pdf_page=7,
        text="Texto completo que no debe enviarse al modelo.",
        printed_label="7",
        image_path="pages/7.png",
        regions=(),
    )
    retriever = FakeRetriever((Chunk("chunk-7", "Fragmento entregado.", (page.evidence_id,)),))
    evidence = FakeEvidenceRepository((page,))
    model = FakeLanguageModel(
        QuestionAnswer("answered", (AnswerBlock("Respuesta.", (page.evidence_id,)),))
    )

    from infrastructure.adapters.outbound.question_workflow.langgraph_workflow import (
        LangGraphQuestionWorkflow,
    )

    trace_id_hex = "a" * 32  # valid 32 lowercase hex chars (Langfuse format)
    workflow = LangGraphQuestionWorkflow(
        retriever=retriever,
        evidence_repository=evidence,
        language_model=model,
        trace_id_factory=lambda: trace_id_hex,
        callback_factory=None,
    )

    execution = asyncio.run(workflow.run(QueryInput("¿Qué indica el manual?", "es")))

    assert execution.trace_id == trace_id_hex
    assert len(recorder.calls) == 1, "the workflow must open exactly one Langfuse observation"
    call = recorder.calls[0]
    assert call["name"] == "question_workflow"
    assert call["trace_context"] == {"trace_id": trace_id_hex}
    assert call["as_type"] == "span"


def test_question_workflow_skips_span_when_trace_id_is_none(monkeypatch: Any) -> None:
    """When ``trace_id_factory`` returns ``None`` no span context is opened."""

    from fakes import FakeEvidenceRepository, FakeLanguageModel, FakeRetriever

    import infrastructure.adapters.outbound.question_workflow.langgraph_workflow as q_mod

    recorder = _install_recording_langfuse(monkeypatch, q_mod)

    from application.models.query import AnswerBlock, QueryInput, QuestionAnswer
    from application.models.retrieval import Chunk
    from domain.models.evidence import PageEvidence

    page = PageEvidence(
        evidence_id="manual:page:7",
        document_hash="a" * 64,
        pdf_page=7,
        text="Texto completo.",
        printed_label="7",
        image_path="pages/7.png",
        regions=(),
    )
    retriever = FakeRetriever((Chunk("chunk-7", "Fragmento.", (page.evidence_id,)),))
    evidence = FakeEvidenceRepository((page,))
    model = FakeLanguageModel(
        QuestionAnswer("answered", (AnswerBlock("Respuesta.", (page.evidence_id,)),))
    )

    from infrastructure.adapters.outbound.question_workflow.langgraph_workflow import (
        LangGraphQuestionWorkflow,
    )

    workflow = LangGraphQuestionWorkflow(
        retriever=retriever,
        evidence_repository=evidence,
        language_model=model,
        trace_id_factory=lambda: None,
        callback_factory=None,
    )

    execution = asyncio.run(workflow.run(QueryInput("Pregunta", "es")))

    assert execution.trace_id is None
    assert recorder.calls == [], "no trace_id must mean no span opened (avoids orphan root traces)"


def test_claim_workflow_opens_langfuse_span_around_graph_dispatch(
    monkeypatch: Any,
) -> None:
    """The claim workflow must wrap ``ainvoke`` in a Langfuse span context.

    Mirrors the question workflow: ``trace_id_factory`` controls the
    ``trace_context`` passed to ``start_as_current_observation``.
    """

    from dataclasses import dataclass

    import infrastructure.adapters.outbound.claim_workflow.langgraph_workflow as c_mod

    recorder = _install_recording_langfuse(monkeypatch, c_mod)

    from application.models.claim import ExtractedClaimFacts
    from application.models.retrieval import Chunk
    from application.ports.outbound.claim_fact_extractor import ClaimFactExtractor
    from application.ports.outbound.evidence_reader import EvidenceReader
    from application.ports.outbound.retriever import RetrievalRequest, Retriever
    from domain.models.claim import ClaimInput
    from domain.models.evidence import PageEvidence

    @dataclass
    class _Extractor(ClaimFactExtractor):
        async def extract(self, claim: ClaimInput) -> ExtractedClaimFacts:
            del claim
            return ExtractedClaimFacts(("A", "B"), ())

    class _Retriever(Retriever):
        async def retrieve(self, request: RetrievalRequest) -> tuple[Chunk, ...]:
            del request
            return (Chunk("criteria", "CIDE exige dos vehículos.", ("manual:page:56",)),)

    @dataclass
    class _Evidence(EvidenceReader):
        page: PageEvidence

        def __post_init__(self) -> None:
            self._pages = {self.page.evidence_id: self.page}

        def get(self, evidence_id: str) -> PageEvidence:
            return self._pages[evidence_id]

    from infrastructure.adapters.outbound.claim_workflow.langgraph_workflow import (
        LangGraphClaimWorkflow,
    )

    trace_id_hex = "b" * 32
    workflow = LangGraphClaimWorkflow(
        fact_extractor=_Extractor(),
        retriever=_Retriever(),
        evidence_repository=_Evidence(
            PageEvidence("manual:page:56", "a" * 64, 56, "texto", None, None, ())
        ),
        trace_id_factory=lambda: trace_id_hex,
        callback_factory=None,
    )

    execution = asyncio.run(workflow.run(ClaimInput("Hubo un accidente entre A y B.")))

    assert execution.trace_id == trace_id_hex
    assert len(recorder.calls) == 1, "the claim workflow must open exactly one Langfuse observation"
    call = recorder.calls[0]
    assert call["name"] == "claim_workflow"
    assert call["trace_context"] == {"trace_id": trace_id_hex}
    assert call["as_type"] == "span"


# Keep ``sys`` import in scope for future monkeypatching hooks (matches the
# other ``from __future__ import annotations`` style).
_ = sys
