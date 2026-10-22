"""Tests for lossless evaluation-turn normalization and resumable runs."""

from __future__ import annotations

import importlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


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
