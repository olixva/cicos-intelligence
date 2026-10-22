"""Baseline runner: ejecuta ``data/evaluation/golden/development.jsonl`` contra el
backend en sus tres modos y aplica los evaluadores deterministas del paquete
``infrastructure.adapters.outbound.evaluation.domain_evaluators``.

Uso::

    # Desde la raíz; carga la misma configuración local que make serve-backend.
    make run-baseline ARGS="--output data/evaluation/results/2026-09-03-baseline-deterministas \\
        --label baseline-deterministas --concurrency 4"

    # Smoke test acotado:
    make run-baseline ARGS="--limit 5 --modes question,claim,auto \\
        --output /tmp/baseline-smoke"

Con ``--judge jev`` (requiere ``TYPESAFE_API_KEY``) añade a ``question`` las
métricas ``jev_context_*`` y ``jev_groundedness*``; ver ``docs/evaluacion.md``.

Resultados::

    <output>/
    ├── manifest.json          # dataset + commit + modelos + ventana temporal
    ├── metrics.json           # agregados por dimensión
    ├── summary.txt            # tabla legible para humanos
    └── per-case/
        └── <case_id>.json     # una línea por caso (modos + métricas por modo)

El script no sobrescribe corridas por accidente. Si la salida ya contiene datos,
``--resume`` exige que coincidan commit, hash del golden, modos, modelos y
configuración; conserva casos completos y reintenta los modos ausentes o con
error técnico.

Decisiones explícitas:
- Concurrencia configurable (default 4, igual que ``ALLIANZ_LANGFUSE_MAX_CONCURRENCY``).
- Errores por caso no detienen el bucle; se cuentan y se reportan en
  ``metrics.json``. ``--resume`` retoma modos incompletos usando el mismo
  manifiesto de identidad.
- Model override: configura los valores en `.env`, o pásalos en `LOCAL_ENV`
  tanto a `make serve-backend` como a `make run-baseline` para fijar un A/B.
- No publica nada a Langfuse: este runner es local, deja los traces en el
  backend (``trace_id`` y ``langfuse_url`` quedan en cada per-case).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.parse import quote
from uuid import uuid4

import httpx

# Permite ``import infrastructure...`` desde ``backend/scripts/``.
_BACKEND_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(_BACKEND_SRC))

# Habilita ``import infrastructure...`` desde ``backend/scripts/``.
_BACKEND_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(_BACKEND_SRC))

from application.models.evaluation import EvaluableTurn, MetricAggregate  # noqa: E402
from application.ports.outbound.decision_model import DecisionModel  # noqa: E402
from application.ports.outbound.language_model import LanguageModelError  # noqa: E402
from application.services.evaluation_normalization import evaluation_error  # noqa: E402
from application.services.evaluation_runtime_config import (  # noqa: E402
    DEFAULT_DOCUMENT_HASH,
    assert_evaluation_runtime_matches,
    evaluation_build_fingerprint,
    evaluation_runtime_configuration,
)
from infrastructure.adapters.outbound.decision_model.jev_client import (  # noqa: E402
    JevDecisionModel,
)
from infrastructure.adapters.outbound.evaluation import jev_judges  # noqa: E402
from infrastructure.adapters.outbound.evaluation.domain_evaluators import (  # noqa: E402
    abstention_metrics,
    decision_accuracy,
    over_resolution_rate_against_reference,
    resolution_support_rate,
    router_confusion_matrix,
)
from infrastructure.adapters.outbound.evaluation.evidence_evaluators import (  # noqa: E402
    citation_id_validity,
    evidence_bundle_coverage,
)
from infrastructure.adapters.outbound.evaluation.golden_schema import (  # noqa: E402
    EvidenceRequirement,
)

# --- Configuración -------------------------------------------------------------

GOLDEN_PATH = Path(__file__).resolve().parents[2] / "data/evaluation/golden/development.jsonl"
DEFAULT_BASE_URL = os.environ.get("ALLIANZ_BASELINE_URL", "http://127.0.0.1:8000")
QUERY_PATH = "/api/v1/queries"
HEALTH_PATH = "/health/ready"
MODES = ("question", "claim", "auto")
JEV_JUDGE_METRICS = frozenset(
    {
        "jev_context_relevance",
        "jev_context_precision",
        "jev_groundedness",
        "jev_groundedness_min",
    }
)
TIMEOUT_S = 180.0
USER_AGENT = "allianz-baseline-runner/0.1"


# --- IO de entrada -------------------------------------------------------------


def _load_golden(limit: int | None) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    with GOLDEN_PATH.open(encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            cases.append(json.loads(line))
            if limit is not None and len(cases) >= limit:
                break
    return cases


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, cwd=GOLDEN_PATH.parent.parent.parent
        ).strip()
    except OSError, subprocess.CalledProcessError:
        return "unknown"


# --- Normalización de predicciones / esperados --------------------------------


def _flatten_facts(result: dict[str, Any]) -> list[str]:
    """Extrae los nombres de hechos (``name``) del ClaimResult serializado."""
    return [str(f.get("name", "")) for f in result.get("facts", []) if isinstance(f, dict)]


def _cited_evidence(result: dict[str, Any]) -> list[str]:
    """Extrae evidence_ids citados en bloques (question o claim)."""
    ids: list[str] = []
    for block in result.get("blocks", []):
        if not isinstance(block, dict):
            continue
        for evidence_id in block.get("evidence_ids", []) or []:
            ids.append(str(evidence_id))
    return ids


def _expected_evidence_pool(case: dict[str, Any]) -> list[str]:
    """Recoge todos los evidence_ids que el golden cita como válidos."""
    return [
        evidence_id
        for requirement in _evidence_requirements(case)
        for bundle in requirement.any_of
        for evidence_id in bundle.all_of
    ]


def _evidence_requirements(case: dict[str, Any]) -> list[EvidenceRequirement]:
    expected = case.get("expected_output") or {}
    raw_requirements = expected.get("evidence_requirements", []) or []
    return [EvidenceRequirement.model_validate(item) for item in raw_requirements]


def _atomic_write_json(path: Path, payload: object) -> None:
    """Replace one JSON file atomically so interruption cannot truncate it."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _write_case_mode(output_dir: Path, case_id: str, mode: str, payload: dict[str, Any]) -> None:
    """Atomically merge one finished mode into its case record."""

    case_path = output_dir / "per-case" / f"{case_id}.json"
    if case_path.exists():
        current = json.loads(case_path.read_text(encoding="utf-8"))
        if not isinstance(current, dict):
            raise ValueError(f"per-case record {case_id!r} is not a JSON object")
    else:
        current = {}
    current[mode] = payload
    _atomic_write_json(case_path, current)


def _load_case_records(output_dir: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    per_case_dir = output_dir / "per-case"
    if not per_case_dir.exists():
        return records
    for path in sorted(per_case_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"per-case record {path.name!r} is not a JSON object")
        records[path.stem] = payload
    return records


def _record_has_error(payload: dict[str, Any] | None) -> bool:
    if payload is None or "error" in payload:
        return True
    evaluation = payload.get("evaluation")
    return not isinstance(evaluation, dict) or evaluation_error(evaluation) is not None


def _pending_modes(
    per_case: dict[str, dict[str, Any]], *, case_ids: tuple[str, ...], modes: tuple[str, ...]
) -> list[tuple[str, str]]:
    """Return missing or failed case/mode pairs in stable input order."""

    return [
        (case_id, mode)
        for case_id in case_ids
        for mode in modes
        if _record_has_error(per_case.get(case_id, {}).get(mode))
    ]


def _run_identity(
    *,
    label: str,
    cases: list[dict[str, Any]],
    modes: tuple[str, ...],
    concurrency: int,
    base_url: str,
    judge: str,
) -> dict[str, Any]:
    commit = _git_commit()
    repo_root = Path(__file__).resolve().parents[2]
    build_fingerprint = evaluation_build_fingerprint(repo_root)
    document_hash = os.environ.get("ALLIANZ_DOCUMENT_HASH", DEFAULT_DOCUMENT_HASH)
    runtime_environment = dict(os.environ)
    runtime_environment["ALLIANZ_BUILD_COMMIT"] = commit
    runtime_environment["ALLIANZ_BUILD_FINGERPRINT"] = build_fingerprint
    effective_configuration = evaluation_runtime_configuration(
        runtime_environment,
        active_index_identity={"index_signature": {"document_hash": document_hash}},
    )
    router_configuration = effective_configuration["router"]
    input_guard_configuration = effective_configuration["input_guard"]
    router_model = router_configuration["model"]
    return {
        "label": label,
        "commit": commit,
        "golden_sha256": sha256(GOLDEN_PATH.read_bytes()).hexdigest(),
        "case_count": len(cases),
        "modes": list(modes),
        "concurrency": concurrency,
        "base_url": base_url,
        "judge": judge,
        "configuration_source": os.environ.get(
            "ALLIANZ_EVALUATION_CONFIG_SOURCE", "process environment"
        ),
        "input_guard": input_guard_configuration,
        "router": router_configuration,
        "models": effective_configuration["models"] | {"router": router_model},
        "effective_configuration": effective_configuration,
    }


def _assert_backend_configuration(expected: dict[str, Any], actual: dict[str, Any]) -> None:
    assert_evaluation_runtime_matches(expected, actual)


def _read_resume_state(
    output_dir: Path, expected_identity: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    manifest_path = output_dir / "manifest.json"
    if not manifest_path.exists():
        raise ValueError("cannot resume: manifest.json is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("run_identity") != expected_identity:
        raise ValueError("cannot resume: run identity does not match manifest.json")
    return manifest, _load_case_records(output_dir)


def _record_run_duration(manifest: dict[str, Any], duration_s: float) -> float:
    """Accumulate every execution segment so resumed runs retain wall-clock time."""

    segments = manifest.get("duration_segments_s")
    if isinstance(segments, list) and all(isinstance(value, (int, float)) for value in segments):
        durations = [float(value) for value in segments]
    else:
        previous = manifest.get("duration_s", 0.0)
        durations = [float(previous)] if isinstance(previous, (int, float)) and previous > 0 else []
    durations.append(duration_s)
    manifest["duration_segments_s"] = durations
    manifest["duration_s"] = sum(durations)
    return manifest["duration_s"]


# --- HTTP ----------------------------------------------------------------------


async def _post_envelope(
    client: httpx.AsyncClient,
    *,
    text: str,
    language: str,
    mode: str,
    session_id: str,
) -> dict[str, Any]:
    payload = {
        "text": text,
        "language": language,
        "mode": mode,
        "session_id": session_id,
    }
    response = await client.post(QUERY_PATH, json=payload, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    return response.json()


async def _wait_for_ready(
    client: httpx.AsyncClient,
    *,
    attempts: int = 30,
    expected_configuration: dict[str, Any] | None = None,
) -> None:
    """Espera a que ``/health/ready`` responda 200 con ``status == ready``."""
    last_error: str = ""
    for _ in range(attempts):
        try:
            response = await client.get(HEALTH_PATH, timeout=2.0)
            if response.status_code == 200:
                body = response.json()
                if body.get("status") == "ready":
                    if expected_configuration is not None:
                        config_response = await client.get("/health/config", timeout=2.0)
                        config_response.raise_for_status()
                        _assert_backend_configuration(
                            expected_configuration, config_response.json()
                        )
                    return
        except (httpx.HTTPError, json.JSONDecodeError) as error:
            last_error = repr(error)
        await asyncio.sleep(1.0)
    raise RuntimeError(
        f"backend no quedó listo tras {attempts}s en {client.base_url}{HEALTH_PATH}: {last_error}"
    )


# --- Métricas por modo ---------------------------------------------------------


def _evaluate_question(*, response: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    result = response.get("result") or {}
    if result.get("kind") != "question":
        return {"error": f"unexpected kind {result.get('kind')!r}"}
    expected = case.get("expected_output") or {}
    expected_status = (expected.get("decisions") or {}).get("answer_status")
    predicted_status = result.get("status")
    cited = _cited_evidence(result)
    pool = _expected_evidence_pool(case)
    requirements = _evidence_requirements(case)
    return {
        "answer_status": predicted_status,
        "answer_status_accuracy": decision_accuracy(
            predicted=predicted_status, expected=expected_status
        ),
        "citation_id_validity": citation_id_validity(
            cited=cited, valid_pool=pool, citations_required=bool(requirements)
        ),
        "evidence_bundle_coverage": evidence_bundle_coverage(
            cited=cited, requirements=requirements
        ),
        "cited_count": len(cited),
        "expected_pool_size": len(pool),
    }


def _evaluate_claim(*, response: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    result = response.get("result") or {}
    if result.get("kind") != "claim":
        return {"error": f"unexpected kind {result.get('kind')!r}"}
    expected = (case.get("expected_output") or {}).get("decisions") or {}
    predicted_facts = _flatten_facts(result)
    cited = _cited_evidence(result)
    pool = _expected_evidence_pool(case)
    requirements = _evidence_requirements(case)
    evaluation: dict[str, Any] = {
        "applicability": result.get("applicability"),
        "convention": result.get("convention"),
        "decision": result.get("decision"),
        "applicability_accuracy": decision_accuracy(
            predicted=result.get("applicability"),
            expected=expected.get("applicability"),
        ),
        "convention_accuracy": decision_accuracy(
            predicted=result.get("convention"),
            expected=expected.get("convention"),
        ),
        "claim_decision_accuracy": decision_accuracy(
            predicted=result.get("decision"),
            expected=expected.get("claim_decision"),
        ),
        "citation_id_validity": citation_id_validity(
            cited=cited, valid_pool=pool, citations_required=bool(requirements)
        ),
        "evidence_bundle_coverage": evidence_bundle_coverage(
            cited=cited, requirements=requirements
        ),
        "cited_count": len(cited),
        "fact_count": len(predicted_facts),
    }
    support_rate = resolution_support_rate(result=result)
    if result.get("decision") != "resolved" or support_rate is not None:
        evaluation["resolution_support_rate"] = support_rate
    return evaluation


def _evaluate_auto(*, response: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    turn = EvaluableTurn.from_envelope(response, requested_mode="auto")
    expected_intent = (case.get("metadata") or {}).get("expected_intent")
    evaluation: dict[str, Any] = {
        "resolved_mode": response.get("resolved_mode"),
        "route_decision": turn.route_decision,
        "result_kind": turn.result_kind,
        "needs_input": turn.needs_input,
        "terminal_status": turn.terminal_status,
        "expected_intent": expected_intent,
        "router_match": (
            decision_accuracy(predicted=turn.route_decision, expected=expected_intent)
            if turn.route_decision is not None
            else None
        ),
    }
    metadata = response.get("metadata")
    if isinstance(metadata, dict):
        for field in ("router_provider", "router_model"):
            value = metadata.get(field)
            if isinstance(value, str):
                evaluation[field] = value
        for field in ("router_input_tokens", "router_output_tokens"):
            value = metadata.get(field)
            if type(value) is int and value >= 0:
                evaluation[field] = value
            elif isinstance(value, str) and value.isdecimal():
                evaluation[field] = int(value)
    return evaluation


# --- Juez Jev (opcional, --judge jev) -----------------------------------------

_PAGE_TEXT_CACHE: dict[str, str] = {}


async def _page_text(client: httpx.AsyncClient, evidence_id: str) -> str:
    if evidence_id not in _PAGE_TEXT_CACHE:
        response = await client.get(f"/api/v1/manual/evidence/{quote(evidence_id, safe='')}")
        response.raise_for_status()
        _PAGE_TEXT_CACHE[evidence_id] = str(response.json().get("text", ""))
    return _PAGE_TEXT_CACHE[evidence_id]


async def _jev_judgements(
    client: httpx.AsyncClient,
    judge: DecisionModel,
    *,
    question: str,
    response: dict[str, Any],
) -> dict[str, float]:
    """Context precision y groundedness de una respuesta documental; vacío si no aplica."""
    result = response.get("result") or {}
    delivered = [str(e["evidence_id"]) for e in response.get("evidence", []) if "evidence_id" in e]
    metrics: dict[str, float] = {}
    if delivered:
        texts = [await _page_text(client, evidence_id) for evidence_id in delivered]
        relevance = await jev_judges.context_relevance(judge, question=question, passages=texts)
        metrics["jev_context_relevance"] = sum(relevance) / len(relevance)
        precision = jev_judges.precision_at_threshold(relevance)
        if precision is not None:
            metrics["jev_context_precision"] = precision
    supported: list[float] = []
    for block in result.get("blocks", []) or []:
        ids = [str(i) for i in block.get("evidence_ids", []) or []]
        if not ids:
            continue
        passages = {f"p{n}": await _page_text(client, i) for n, i in enumerate(ids, start=1)}
        supported.append(
            await jev_judges.groundedness(
                judge, claim=str(block.get("text", "")), passages=passages
            )
        )
    if supported:
        metrics["jev_groundedness"] = sum(supported) / len(supported)
        metrics["jev_groundedness_min"] = min(supported)
    return metrics


# --- Orquestación --------------------------------------------------------------


async def _run_one(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    *,
    case: dict[str, Any],
    mode: str,
    judge: DecisionModel | None = None,
) -> tuple[str, str, dict[str, Any], float]:
    case_id = (case.get("metadata") or {}).get("case_id") or "unknown"
    start = time.monotonic()
    try:
        async with semaphore:
            response = await _post_envelope(
                client,
                text=(case.get("input") or {}).get("text", ""),
                language=(case.get("input") or {}).get("language", "es"),
                mode=mode,
                session_id=f"baseline-{case_id}-{mode}",
            )
        turn = EvaluableTurn.from_envelope(response, requested_mode=mode)
        if turn.technical_error is not None:
            return (
                case_id,
                mode,
                {"error": turn.technical_error},
                time.monotonic() - start,
            )
        if mode == "question":
            evaluation = _evaluate_question(response=response, case=case)
            if judge is not None and "error" not in evaluation:
                try:
                    evaluation.update(
                        await _jev_judgements(
                            client,
                            judge,
                            question=(case.get("input") or {}).get("text", ""),
                            response=response,
                        )
                    )
                except (LanguageModelError, httpx.HTTPError) as judge_error:
                    # Un fallo del juez no invalida el caso: se anota y se sigue.
                    evaluation["jev_judge_error"] = repr(judge_error)
        elif mode == "claim":
            evaluation = _evaluate_claim(response=response, case=case)
        else:
            evaluation = _evaluate_auto(response=response, case=case)
        evaluation_failure = evaluation_error(evaluation)
        payload: dict[str, Any] = {
            "response": response,
            "turn": {
                "route_decision": turn.route_decision,
                "result_kind": turn.result_kind,
                "needs_input": turn.needs_input,
                "terminal_status": turn.terminal_status,
            },
            "evaluation": evaluation,
        }
        if evaluation_failure is not None:
            payload["error"] = evaluation_failure
        return (
            case_id,
            mode,
            payload,
            time.monotonic() - start,
        )
    except (httpx.HTTPError, json.JSONDecodeError, KeyError, ValueError) as error:  # noqa: BLE001
        turn = EvaluableTurn.from_error(error)
        return (
            case_id,
            mode,
            {
                "error": turn.technical_error,
            },
            time.monotonic() - start,
        )


async def _run_all(
    *,
    cases: list[dict[str, Any]],
    modes: tuple[str, ...],
    concurrency: int,
    base_url: str,
    judge: DecisionModel | None = None,
    pending_modes: list[tuple[str, str]] | None = None,
    output_dir: Path | None = None,
    expected_configuration: dict[str, Any] | None = None,
) -> list[tuple[str, str, dict[str, Any], float]]:
    semaphore = asyncio.Semaphore(concurrency)
    selected_modes = set(pending_modes) if pending_modes is not None else None

    async def run_and_persist(
        client: httpx.AsyncClient, *, case: dict[str, Any], mode: str
    ) -> tuple[str, str, dict[str, Any], float]:
        result = await _run_one(client, semaphore, case=case, mode=mode, judge=judge)
        if output_dir is not None:
            case_id, result_mode, payload, elapsed_s = result
            _write_case_mode(
                output_dir,
                case_id,
                result_mode,
                {**payload, "elapsed_s": elapsed_s},
            )
        return result

    async with httpx.AsyncClient(base_url=base_url, timeout=TIMEOUT_S) as client:
        await _wait_for_ready(client, expected_configuration=expected_configuration)
        tasks = [
            asyncio.create_task(run_and_persist(client, case=case, mode=mode))
            for case in cases
            for mode in modes
            if selected_modes is None
            or ((case.get("metadata") or {}).get("case_id") or "unknown", mode) in selected_modes
        ]
        return await asyncio.gather(*tasks)


# --- Agregación ----------------------------------------------------------------


def _aggregate(
    per_case: dict[str, dict[str, Any]],
    cases_lookup: dict[str, dict[str, Any]],
    *,
    modes: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Aggregate every requested case while retaining missing/error outcomes."""
    selected_modes = modes or tuple(
        mode for mode in MODES if any(mode in records for records in per_case.values())
    )
    known_metrics = {
        "question": {
            "answer_status_accuracy",
            "citation_id_validity",
            "evidence_bundle_coverage",
            "cited_count",
            "expected_pool_size",
        },
        "claim": {
            "applicability_accuracy",
            "convention_accuracy",
            "claim_decision_accuracy",
            "citation_id_validity",
            "evidence_bundle_coverage",
            "cited_count",
            "fact_count",
            "resolution_support_rate",
        },
        "auto": {"router_match"},
    }
    aggregated: dict[str, Any] = {}
    for mode in selected_modes:
        metric_names = set(known_metrics.get(mode, set()))
        for records in per_case.values():
            payload = records.get(mode)
            evaluation = payload.get("evaluation") if isinstance(payload, dict) else None
            if not isinstance(evaluation, dict):
                continue
            if isinstance(evaluation.get("jev_judge_error"), str):
                metric_names.update(JEV_JUDGE_METRICS)
            metric_names.update(
                key
                for key, value in evaluation.items()
                if (isinstance(value, (int, float)) and not isinstance(value, bool))
                or value is None
            )

        mode_errors = sum(
            1
            for case_id in cases_lookup
            if (payload := per_case.get(case_id, {}).get(mode)) is not None
            and _record_has_error(payload)
        )
        mode_missing_cases = sum(
            per_case.get(case_id, {}).get(mode) is None for case_id in cases_lookup
        )
        metric_summaries: dict[str, Any] = {}
        for metric_name in sorted(metric_names):
            scored_values: list[float] = []
            n_missing = 0
            n_error = 0
            n_not_applicable = 0
            for case_id in cases_lookup:
                payload = per_case.get(case_id, {}).get(mode)
                if payload is None:
                    n_missing += 1
                    continue
                if _record_has_error(payload):
                    n_error += 1
                    continue
                evaluation = payload.get("evaluation")
                if not isinstance(evaluation, dict) or metric_name not in evaluation:
                    if (
                        metric_name in JEV_JUDGE_METRICS
                        and isinstance(evaluation, dict)
                        and isinstance(evaluation.get("jev_judge_error"), str)
                    ):
                        n_error += 1
                        continue
                    n_missing += 1
                    continue
                value = evaluation[metric_name]
                if value is None:
                    if metric_name == "router_match" and isinstance(
                        evaluation.get("expected_intent"), str
                    ):
                        n_missing += 1
                    else:
                        n_not_applicable += 1
                elif isinstance(value, (int, float)) and not isinstance(value, bool):
                    scored_values.append(float(value))
                else:
                    n_missing += 1

            metric_aggregate = MetricAggregate.from_outcomes(
                scored_values=scored_values,
                n_missing=n_missing,
                n_error=n_error,
                n_not_applicable=n_not_applicable,
            )
            metric_summaries[metric_name] = {
                **asdict(metric_aggregate),
                "min": min(scored_values, default=None),
                "max": max(scored_values, default=None),
            }
        aggregated[mode] = {
            "cases_total": len(cases_lookup),
            "errors": mode_errors,
            "missing_cases": mode_missing_cases,
            "metrics": metric_summaries,
        }

    # Métricas compuestas entre modos. Los outcomes sin decisión se conservan
    # como missing/error en vez de desaparecer del denominador.
    predicted_routes: list[str] = []
    expected_routes: list[str] = []
    router_missing = 0
    router_cases = 0
    router_correct = 0
    over_resolution_values: list[float] = []
    over_resolution_missing = 0
    over_resolution_errors = 0
    over_resolution_not_applicable = 0
    paired: list[tuple[str, str]] = []
    for case_id, case in cases_lookup.items():
        expected_intent = (case.get("metadata") or {}).get("expected_intent")
        auto = per_case.get(case_id, {}).get("auto")
        if "auto" in selected_modes and isinstance(expected_intent, str) and expected_intent:
            router_cases += 1
            if auto is None or _record_has_error(auto):
                router_missing += 1
            else:
                auto_evaluation = auto.get("evaluation")
                route = (
                    auto_evaluation.get("route_decision")
                    if isinstance(auto_evaluation, dict)
                    else None
                )
                if isinstance(route, str) and route in {
                    "question",
                    "claim",
                    "clarification_required",
                }:
                    predicted_routes.append(route)
                    expected_routes.append(expected_intent)
                    router_correct += route == expected_intent
                else:
                    router_missing += 1

        if "claim" not in selected_modes:
            continue
        expected_decision = ((case.get("expected_output") or {}).get("decisions") or {}).get(
            "claim_decision"
        )
        claim = per_case.get(case_id, {}).get("claim")
        if not isinstance(expected_decision, str) or not expected_decision:
            over_resolution_not_applicable += 1
            continue
        if claim is None:
            over_resolution_missing += 1
            continue
        if _record_has_error(claim):
            over_resolution_errors += 1
            continue
        claim_evaluation = claim.get("evaluation")
        predicted = claim_evaluation.get("decision") if isinstance(claim_evaluation, dict) else None
        if not isinstance(predicted, str) or not predicted:
            over_resolution_missing += 1
            continue
        score = over_resolution_rate_against_reference(
            predicted_decisions=[predicted], expected_decisions=[expected_decision]
        )
        if score is not None:
            over_resolution_values.append(score)
            paired.append((predicted, expected_decision))

    cm = router_confusion_matrix(
        predicted_routes=predicted_routes,
        expected_routes=expected_routes,
    )
    cm_json = {f"{expected}|{predicted}": n for (expected, predicted), n in cm.items()}

    over_resolution_aggregate = MetricAggregate.from_outcomes(
        scored_values=over_resolution_values,
        n_missing=over_resolution_missing,
        n_error=over_resolution_errors,
        n_not_applicable=over_resolution_not_applicable,
    )

    aggregated["cross_mode"] = {
        "router_confusion_matrix": cm_json,
        "abstention": {
            "correct_rate": abstention_metrics(
                predicted_decisions=[p for p, _ in paired],
                expected_decisions=[e for _, e in paired],
            )[0]
        },
        "over_resolution_rate_against_reference": asdict(over_resolution_aggregate),
        "router_cases": router_cases,
        "router_missing": router_missing,
        "router_end_to_end_accuracy_all_labeled": {
            "scope": "auto pipeline: dispatch and response availability as well as route",
            "n_labeled": router_cases,
            "n_predicted": router_cases - router_missing,
            "n_missing_or_error": router_missing,
            "n_correct": router_correct,
            "n_incorrect": router_cases - router_correct,
            "accuracy": (router_correct / router_cases if router_cases else None),
        },
    }
    return aggregated


def _write_summary(
    metrics: dict[str, Any],
    *,
    cases_total: int,
    modes: tuple[str, ...],
    label: str,
    duration_s: float,
) -> str:
    lines: list[str] = []
    lines.append(f"# Baseline runner — {label}")
    lines.append("")
    lines.append(f"Casos: {cases_total} · modos: {','.join(modes)} · duración: {duration_s:.1f}s")
    lines.append("")
    for mode in modes:
        block = metrics.get(mode) or {}
        total = block.get("cases_total", 0)
        errors = block.get("errors", 0)
        missing_cases = block.get("missing_cases", 0)
        lines.append(f"## {mode} ({total - errors - missing_cases}/{total} completos)")
        metric_blocks = block.get("metrics") or {}
        if not metric_blocks:
            lines.append("  (sin métricas)")
            continue
        for key, summary in metric_blocks.items():
            mean = summary.get("mean")
            mean_str = f"{mean:.3f}" if mean is not None else "n/a"
            lines.append(
                f"  - {key}: mean={mean_str} "
                f"(scored={summary['n_scored']}, applicable={summary['n_applicable']}, "
                f"total={summary['n_total']}, missing={summary['n_missing']}, "
                f"error={summary['n_error']}, not_applicable={summary['n_not_applicable']}, "
                f"min={summary['min']}, max={summary['max']})"
            )
    lines.append("")
    cross = metrics.get("cross_mode") or {}
    router_accuracy = cross.get("router_end_to_end_accuracy_all_labeled") or {}
    accuracy = router_accuracy.get("accuracy")
    accuracy_text = f"{accuracy:.3f}" if isinstance(accuracy, (int, float)) else "n/a"
    lines.append(
        "## router_end_to_end_accuracy_all_labeled "
        f"accuracy={accuracy_text} ({router_accuracy.get('n_correct', 0)}/"
        f"{router_accuracy.get('n_labeled', 0)}; "
        f"missing_or_error={router_accuracy.get('n_missing_or_error', 0)})"
    )
    cm = cross.get("router_confusion_matrix") or {}
    lines.append(f"## router_confusion_matrix ({cross.get('router_cases', 0)} casos en auto)")
    if cm:
        for key, n in sorted(cm.items()):
            expected, predicted = key.split("|", 1)
            lines.append(f"  - expected={expected} predicted={predicted} -> {n}")
    else:
        lines.append("  (vacía)")
    return "\n".join(lines) + "\n"


# --- Main ----------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--limit", type=int, default=None, help="Sólo los primeros N casos (smoke test)."
    )
    parser.add_argument("--modes", default=",".join(MODES), help="Modos separados por coma.")
    parser.add_argument(
        "--output", required=True, help="Carpeta nueva de salida o corrida parcial para reanudar."
    )
    parser.add_argument(
        "--resume", action="store_true", help="Reanuda una corrida con identidad idéntica."
    )
    parser.add_argument("--label", default="baseline", help="Etiqueta corta de la corrida.")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument(
        "--judge",
        choices=("none", "jev"),
        default="none",
        help="'jev' añade context precision y groundedness (requiere TYPESAFE_API_KEY).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    output_dir = Path(args.output).resolve()
    modes = tuple(m for m in args.modes.split(",") if m in MODES)
    if not modes:
        raise SystemExit(f"--modes debe contener al menos uno de {MODES}")

    cases = _load_golden(args.limit)
    identity = _run_identity(
        label=args.label,
        cases=cases,
        modes=modes,
        concurrency=args.concurrency,
        base_url=args.base_url,
        judge=args.judge,
    )
    output_exists_with_data = output_dir.exists() and any(output_dir.iterdir())
    if output_exists_with_data:
        if not args.resume:
            raise SystemExit(
                f"Output dir {output_dir} ya contiene datos; usa --resume o elige otra carpeta."
            )
        try:
            manifest, per_case = _read_resume_state(output_dir, identity)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise SystemExit(str(error)) from error
    else:
        manifest = {
            "label": args.label,
            "started_at": datetime.now(UTC).isoformat(),
            "run_identity": identity,
            "status": "running",
            "resume_count": 0,
        }
        per_case = {}

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "per-case").mkdir(exist_ok=True)
    manifest["status"] = "running"
    manifest["resume_count"] = int(manifest.get("resume_count", 0)) + int(output_exists_with_data)
    _atomic_write_json(output_dir / "manifest.json", manifest)

    case_ids = tuple(
        str((case.get("metadata") or {}).get("case_id") or "unknown") for case in cases
    )
    pending = _pending_modes(per_case, case_ids=case_ids, modes=modes)
    print(
        f"[baseline] {len(cases)} casos, modos={modes}, concurrency={args.concurrency}, "
        f"pendientes={len(pending)}, base_url={args.base_url}",
        flush=True,
    )

    wall_start = time.monotonic()
    if pending:
        asyncio.run(
            _run_all(
                cases=cases,
                modes=modes,
                concurrency=args.concurrency,
                base_url=args.base_url,
                judge=JevDecisionModel() if args.judge == "jev" else None,
                pending_modes=pending,
                output_dir=output_dir,
                expected_configuration=identity["effective_configuration"],
            )
        )
    duration_s = time.monotonic() - wall_start
    per_case = _load_case_records(output_dir)

    metrics = _aggregate(
        per_case,
        {str(c.get("metadata", {}).get("case_id")): c for c in cases},
        modes=modes,
    )
    remaining = _pending_modes(per_case, case_ids=case_ids, modes=modes)
    total_duration_s = _record_run_duration(manifest, duration_s)
    manifest.update(
        {
            "duration_s": total_duration_s,
            "run_identity": identity,
            "status": "complete" if not remaining else "partial",
            "pending_case_modes": len(remaining),
            "models": identity["models"],
            "router": identity["router"],
            "input_guard": identity["input_guard"],
            "commit": identity["commit"],
            "golden_path": str(GOLDEN_PATH),
            "golden_sha256": identity["golden_sha256"],
            "case_count": len(cases),
            "modes": list(modes),
            "concurrency": args.concurrency,
            "base_url": args.base_url,
            "judge": args.judge,
            "configuration_source": identity["configuration_source"],
        }
    )
    _atomic_write_json(output_dir / "manifest.json", manifest)
    _atomic_write_json(output_dir / "metrics.json", metrics)
    summary = _write_summary(
        metrics,
        cases_total=len(cases),
        modes=modes,
        label=args.label,
        duration_s=total_duration_s,
    )
    summary_path = output_dir / "summary.txt"
    temporary_summary = summary_path.with_name(f".{summary_path.name}.{uuid4().hex}.tmp")
    temporary_summary.write_text(summary, encoding="utf-8")
    os.replace(temporary_summary, summary_path)

    print(
        f"[baseline] {'ok' if not remaining else 'parcial'} en "
        f"{total_duration_s:.1f}s — {output_dir}",
        flush=True,
    )
    print(summary)
    return 0 if not remaining else 1


if __name__ == "__main__":
    raise SystemExit(main())
