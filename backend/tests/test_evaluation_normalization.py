"""Tests for lossless evaluation-turn normalization and resumable runs."""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import httpx
import pytest


def _evaluatable_turn_type():
    spec = importlib.util.find_spec("application.models.evaluation")
    assert spec is not None, "evaluation model module must exist"
    module = importlib.import_module("application.models.evaluation")
    assert hasattr(module, "EvaluableTurn"), "evaluation model must define EvaluableTurn"
    return module.EvaluableTurn


def _baseline_module() -> ModuleType:
    script_path = Path(__file__).parents[1] / "scripts" / "run_baseline.py"
    spec = importlib.util.spec_from_file_location("allianz_test_run_baseline", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_auto_claim_clarification_keeps_route_decision() -> None:
    EvaluableTurn = _evaluatable_turn_type()
    response = {
        "requested_mode": "auto",
        "resolved_mode": "claim",
        "result": {
            "kind": "claim",
            "decision": "conditional",
            "missing_information": ["casillas DAA"],
        },
        "metadata": {},
    }

    turn = EvaluableTurn.from_envelope(response, requested_mode="auto")

    assert turn.route_decision == "claim"
    assert turn.result_kind == "claim"
    assert turn.needs_input is True
    assert turn.terminal_status == "conditional"
    assert turn.technical_error is None


def test_http_error_is_preserved_as_technical_error() -> None:
    EvaluableTurn = _evaluatable_turn_type()

    turn = EvaluableTurn.from_error(TimeoutError("provider timed out"))

    assert turn.technical_error == "TimeoutError"
    assert "provider timed out" not in turn.technical_error
    assert turn.result_kind is None
    assert turn.needs_input is False


def test_auto_guardrail_is_not_counted_as_router_decision() -> None:
    runner = _baseline_module()
    response = {
        "requested_mode": "auto",
        "resolved_mode": "clarification",
        "result": {"kind": "clarification", "message": "Fuera de alcance."},
        "metadata": {"guardrail": "blocked"},
    }
    case = {"metadata": {"expected_intent": "question"}}

    evaluation = runner._evaluate_auto(response=response, case=case)

    assert evaluation["route_decision"] is None
    assert evaluation["router_match"] is None


def test_auto_evaluation_records_router_provider_and_token_usage() -> None:
    runner = _baseline_module()
    response = {
        "requested_mode": "auto",
        "resolved_mode": "claim",
        "result": {"kind": "claim", "decision": "conditional"},
        "metadata": {
            "router_provider": "typesafe",
            "router_model": "jev-production",
            "router_input_tokens": 22,
            "router_output_tokens": 4,
        },
    }

    evaluation = runner._evaluate_auto(
        response=response, case={"metadata": {"expected_intent": "claim"}}
    )

    assert evaluation["router_provider"] == "typesafe"
    assert evaluation["router_model"] == "jev-production"
    assert evaluation["router_input_tokens"] == 22
    assert evaluation["router_output_tokens"] == 4


def test_unknown_metric_does_not_abort_aggregation() -> None:
    runner = _baseline_module()
    per_case = {
        "case-1": {
            "claim": {
                "evaluation": {"error": "unsupported evaluator"},
            }
        }
    }

    aggregated = runner._aggregate(per_case, {"case-1": {}})

    assert aggregated["claim"]["cases_total"] == 1
    assert aggregated["claim"]["errors"] == 1


def test_resume_reuses_complete_records_and_retries_errors(tmp_path: Path) -> None:
    runner = _baseline_module()
    output_dir = tmp_path / "run"
    case_dir = output_dir / "per-case"
    case_dir.mkdir(parents=True)
    identity = {"label": "baseline", "commit": "abc123"}
    runner._atomic_write_json(output_dir / "manifest.json", {"run_identity": identity})
    runner._atomic_write_json(
        case_dir / "case-1.json",
        {
            "question": {"evaluation": {"answer_status_accuracy": 1.0}},
            "claim": {"error": "provider unavailable"},
        },
    )

    manifest, saved_records = runner._read_resume_state(output_dir, identity)
    assert manifest["run_identity"] == identity
    pending = runner._pending_modes(
        saved_records,
        case_ids=("case-1",),
        modes=("question", "claim", "auto"),
    )

    assert pending == [("case-1", "claim"), ("case-1", "auto")]


def test_case_json_is_atomically_replaced(tmp_path: Path) -> None:
    runner = _baseline_module()
    case_dir = tmp_path / "per-case"
    case_dir.mkdir()

    runner._write_case_mode(tmp_path, "case-1", "question", {"evaluation": {"score": 1.0}})
    runner._write_case_mode(tmp_path, "case-1", "claim", {"error": "temporary"})

    saved = json.loads((case_dir / "case-1.json").read_text(encoding="utf-8"))
    assert set(saved) == {"question", "claim"}
    assert saved["question"]["evaluation"]["score"] == 1.0
    assert list(case_dir.iterdir()) == [case_dir / "case-1.json"]


def test_run_identity_records_router_provider_model_and_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = _baseline_module()
    monkeypatch.delenv("OPENAI_ANSWER_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_CLAIM_EXTRACTION_MODEL", raising=False)
    monkeypatch.delenv("ALLIANZ_ROUTER_MODEL", raising=False)
    monkeypatch.setenv("ALLIANZ_ROUTER_BACKEND", "jev")
    monkeypatch.setenv("TYPESAFE_DEFAULT_MODEL", "jev-test-model")
    monkeypatch.setenv("ALLIANZ_JEV_ROUTER_MIN_CONFIDENCE", "0.75")
    monkeypatch.setenv("ALLIANZ_INPUT_GUARD", "jev")
    monkeypatch.setenv("ALLIANZ_JEV_GUARD_INJECTION", "0.81")
    monkeypatch.setenv("ALLIANZ_JEV_GUARD_OFF_TOPIC", "0.93")
    monkeypatch.setenv("ALLIANZ_EVALUATION_CONFIG_SOURCE", "makefile:.env+ops/local.env+LOCAL_ENV")

    identity = runner._run_identity(
        label="router-jev",
        cases=[],
        modes=("auto",),
        concurrency=1,
        base_url="http://test",
        judge="none",
    )

    assert identity["router"] == {
        "backend": "jev",
        "model": "jev-test-model",
        "min_confidence": 0.75,
    }
    assert identity["models"]["answer"] == "gpt-6.1-sol"
    assert identity["models"]["extraction"] == "gpt-6.1-sol"
    assert identity["models"]["router"] == "jev-test-model"
    assert identity["configuration_source"] == "makefile:.env+ops/local.env+LOCAL_ENV"
    assert identity["input_guard"] == {
        "backend": "jev",
        "injection_threshold": 0.81,
        "off_topic_threshold": 0.93,
    }

    monkeypatch.setenv("ALLIANZ_ROUTER_BACKEND", "openai")
    openai_identity = runner._run_identity(
        label="router-openai",
        cases=[],
        modes=("auto",),
        concurrency=1,
        base_url="http://test",
        judge="none",
    )
    assert openai_identity["router"] == {
        "backend": "openai",
        "model": "gpt-6-luna",
        "min_confidence": None,
    }


def test_run_identity_defaults_to_jev_router_and_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _baseline_module()
    for name in (
        "ALLIANZ_ROUTER_BACKEND",
        "TYPESAFE_DEFAULT_MODEL",
        "ALLIANZ_JEV_ROUTER_MIN_CONFIDENCE",
        "ALLIANZ_INPUT_GUARD",
        "ALLIANZ_JEV_GUARD_INJECTION",
        "ALLIANZ_JEV_GUARD_OFF_TOPIC",
    ):
        monkeypatch.delenv(name, raising=False)

    identity = runner._run_identity(
        label="defaults",
        cases=[],
        modes=("auto",),
        concurrency=1,
        base_url="http://test",
        judge="none",
    )

    assert identity["router"] == {
        "backend": "jev",
        "model": "jev-latest",
        "min_confidence": 0.4,
    }
    assert identity["input_guard"] == {
        "backend": "jev",
        "injection_threshold": 0.9,
        "off_topic_threshold": 0.95,
    }


def test_router_promotion_accuracy_counts_missing_routes_and_errors_as_incorrect() -> None:
    runner = _baseline_module()
    cases = {
        "correct": {"metadata": {"expected_intent": "claim"}},
        "error": {"metadata": {"expected_intent": "question"}},
        "missing": {"metadata": {"expected_intent": "question"}},
        "unlabeled": {"metadata": {}},
    }
    per_case = {
        "correct": {
            "auto": {
                "evaluation": {
                    "expected_intent": "claim",
                    "route_decision": "claim",
                    "router_match": 1.0,
                }
            }
        },
        "error": {"auto": {"error": "TimeoutError"}},
        "missing": {
            "auto": {
                "evaluation": {
                    "expected_intent": "question",
                    "route_decision": None,
                    "router_match": None,
                }
            }
        },
    }

    metrics = runner._aggregate(per_case, cases, modes=("auto",))

    assert metrics["cross_mode"]["router_end_to_end_accuracy_all_labeled"] == {
        "scope": "auto pipeline: dispatch and response availability as well as route",
        "n_labeled": 3,
        "n_predicted": 1,
        "n_missing_or_error": 2,
        "n_correct": 1,
        "n_incorrect": 2,
        "accuracy": pytest.approx(1 / 3),
    }
    assert "router_accuracy_all_labeled" not in metrics["cross_mode"]


def test_runner_rejects_backend_configuration_mismatch() -> None:
    runner = _baseline_module()
    expected = {
        "router": {"backend": "jev", "model": "jev-latest", "min_confidence": 0.4},
        "input_guard": {
            "backend": "jev",
            "injection_threshold": 0.9,
            "off_topic_threshold": 0.95,
        },
        "models": {"answer": "gpt-6-luna", "extraction": "gpt-6-luna"},
    }
    actual = {
        **expected,
        "router": {"backend": "openai", "model": "gpt-6-luna", "min_confidence": None},
    }

    with pytest.raises(RuntimeError, match="router.backend"):
        runner._assert_backend_configuration(expected, actual)


def test_resume_adds_run_time_instead_of_replacing_partial_duration() -> None:
    runner = _baseline_module()
    manifest = {"duration_s": 120.0}

    total = runner._record_run_duration(manifest, 8.5)

    assert total == pytest.approx(128.5)
    assert manifest["duration_segments_s"] == [120.0, 8.5]
    assert manifest["duration_s"] == pytest.approx(128.5)


def test_runner_checks_live_configuration_before_sending_cases() -> None:
    runner = _baseline_module()
    expected = {
        "router": {"backend": "jev", "model": "jev-latest", "min_confidence": 0.4},
        "input_guard": {
            "backend": "jev",
            "injection_threshold": 0.9,
            "off_topic_threshold": 0.95,
        },
        "models": {"answer": "gpt-6-luna", "extraction": "gpt-6-luna"},
    }

    async def response(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health/ready":
            return httpx.Response(200, json={"status": "ready"})
        return httpx.Response(
            200,
            json={
                **expected,
                "router": {
                    "backend": "openai",
                    "model": "gpt-6-luna",
                    "min_confidence": None,
                },
            },
        )

    async def check() -> None:
        async with httpx.AsyncClient(
            base_url="http://test", transport=httpx.MockTransport(response)
        ) as client:
            with pytest.raises(RuntimeError, match="router.backend"):
                await runner._wait_for_ready(client, attempts=1, expected_configuration=expected)

    asyncio.run(check())


def test_jev_judge_failures_are_counted_without_invalidating_deterministic_case() -> None:
    runner = _baseline_module()
    metrics = runner._aggregate(
        {
            "question-1": {
                "question": {
                    "evaluation": {
                        "answer_status_accuracy": 1.0,
                        "jev_judge_error": "LanguageModelError",
                    }
                }
            }
        },
        {"question-1": {"expected_output": {"status": "answered"}}},
        modes=("question",),
    )

    question = metrics["question"]
    assert question["errors"] == 0
    assert question["metrics"]["answer_status_accuracy"]["mean"] == 1.0
    assert question["metrics"]["jev_context_precision"]["n_error"] == 1
    assert question["metrics"]["jev_groundedness"]["n_error"] == 1
