"""Baseline runner: ejecuta ``data/evaluation/golden/development.jsonl`` contra el
backend en sus tres modos y aplica los evaluadores deterministas del paquete
``infrastructure.adapters.outbound.evaluation.domain_evaluators``.

Uso::

    # Asume backend levantado en 127.0.0.1:8000 y extractiones cargadas.
    cd backend && uv run --no-sync python scripts/run_baseline.py \\
        --output ../data/evaluation/results/2026-09-03-baseline-deterministas \\
        --label baseline-deterministas \\
        --concurrency 4

    # Smoke test acotado:
    cd backend && uv run --no-sync python scripts/run_baseline.py \\
        --limit 5 --modes question,claim,auto \\
        --output /tmp/baseline-smoke

Resultados::

    <output>/
    ├── manifest.json          # dataset + commit + modelos + ventana temporal
    ├── metrics.json           # agregados por dimensión
    ├── summary.txt            # tabla legible para humanos
    └── per-case/
        └── <case_id>.json     # una línea por caso (modos + métricas por modo)

El script es idempotente: si la carpeta de salida ya existe, falla con un error
claro. Reanudar parcial requiere borrar o renombrar la carpeta de salida.

Decisiones explícitas:
- Concurrencia configurable (default 4, igual que ``ALLIANZ_LANGFUSE_MAX_CONCURRENCY``).
- Errores por caso no detienen el bucle; se cuentan y se reportan en
  ``metrics.json``.
- Model override: el script no toca variables; arráncalo con
  ``OPENAI_ANSWER_MODEL=gpt-5.6-luna OPENAI_CLAIM_EXTRACTION_MODEL=gpt-5.6-luna``
  antes de levantar el backend para iterar barato.
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
import traceback
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

# Permite ``import infrastructure...`` desde ``backend/scripts/``.
_BACKEND_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(_BACKEND_SRC))

# Habilita ``import infrastructure...`` desde ``backend/scripts/``.
_BACKEND_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(_BACKEND_SRC))

from infrastructure.adapters.outbound.evaluation.domain_evaluators import (  # noqa: E402
    abstention_metrics,
    decision_accuracy,
    evidence_reference_validity,
    invented_facts_rate,
    router_confusion_matrix,
    unjustified_resolution_rate,
)

# --- Configuración -------------------------------------------------------------

GOLDEN_PATH = Path("/Users/aoc/proyectos/prueba-allianz/data/evaluation/golden/development.jsonl")
DEFAULT_BASE_URL = os.environ.get("ALLIANZ_BASELINE_URL", "http://127.0.0.1:8000")
QUERY_PATH = "/api/v1/queries"
HEALTH_PATH = "/health/ready"
MODES = ("question", "claim", "auto")
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
    expected = case.get("expected_output") or {}
    pool: list[str] = []
    for requirement in expected.get("evidence_requirements", []) or []:
        for bundle in requirement.get("any_of", []) or []:
            for evidence_id in bundle.get("all_of", []) or []:
                pool.append(str(evidence_id))
    return pool


def _expected_forbidden_facts(case: dict[str, Any]) -> list[str]:
    expected = case.get("expected_output") or {}
    return [str(f) for f in expected.get("forbidden_facts", []) or []]


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


async def _wait_for_ready(client: httpx.AsyncClient, *, attempts: int = 30) -> None:
    """Espera a que ``/health/ready`` responda 200 con ``status == ready``."""
    last_error: str = ""
    for _ in range(attempts):
        try:
            response = await client.get(HEALTH_PATH, timeout=2.0)
            if response.status_code == 200:
                body = response.json()
                if body.get("status") == "ready":
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
    return {
        "answer_status": predicted_status,
        "answer_status_accuracy": decision_accuracy(
            predicted=predicted_status, expected=expected_status
        ),
        "evidence_validity": evidence_reference_validity(cited=cited, valid_pool=pool),
        "cited_count": len(cited),
        "expected_pool_size": len(pool),
    }


def _evaluate_claim(*, response: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    result = response.get("result") or {}
    if result.get("kind") != "claim":
        return {"error": f"unexpected kind {result.get('kind')!r}"}
    expected = (case.get("expected_output") or {}).get("decisions") or {}
    predicted_facts = _flatten_facts(result)
    expected_fact_names = [
        str(f.get("name", "")) for f in (case.get("expected_output") or {}).get("facts", []) or []
    ]
    forbidden = _expected_forbidden_facts(case)
    cited = _cited_evidence(result)
    pool = _expected_evidence_pool(case)
    return {
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
        "invented_facts_rate": invented_facts_rate(
            predicted_facts=predicted_facts,
            expected_facts=expected_fact_names,
            forbidden_facts=forbidden,
        ),
        "evidence_validity": evidence_reference_validity(cited=cited, valid_pool=pool),
        "cited_count": len(cited),
        "fact_count": len(predicted_facts),
    }


def _evaluate_auto(*, response: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    resolved = response.get("resolved_mode")
    expected_intent = (case.get("metadata") or {}).get("expected_intent")
    return {
        "resolved_mode": resolved,
        "expected_intent": expected_intent,
        "router_match": decision_accuracy(predicted=resolved, expected=expected_intent),
    }


# --- Orquestación --------------------------------------------------------------


async def _run_one(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    *,
    case: dict[str, Any],
    mode: str,
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
        if mode == "question":
            evaluation = _evaluate_question(response=response, case=case)
        elif mode == "claim":
            evaluation = _evaluate_claim(response=response, case=case)
        else:
            evaluation = _evaluate_auto(response=response, case=case)
        return (
            case_id,
            mode,
            {"response": response, "evaluation": evaluation},
            time.monotonic() - start,
        )
    except (httpx.HTTPError, json.JSONDecodeError, KeyError, ValueError) as error:  # noqa: BLE001
        return (
            case_id,
            mode,
            {
                "error": repr(error),
                "traceback": traceback.format_exc(limit=4),
            },
            time.monotonic() - start,
        )


async def _run_all(
    *,
    cases: list[dict[str, Any]],
    modes: tuple[str, ...],
    concurrency: int,
    base_url: str,
) -> list[tuple[str, str, dict[str, Any], float]]:
    semaphore = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient(base_url=base_url, timeout=TIMEOUT_S) as client:
        await _wait_for_ready(client)
        tasks = [
            asyncio.create_task(_run_one(client, semaphore, case=case, mode=mode))
            for case in cases
            for mode in modes
        ]
        return await asyncio.gather(*tasks)


# --- Agregación ----------------------------------------------------------------


def _aggregate(
    per_case: dict[str, dict[str, Any]], cases_lookup: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Suma métricas a nivel de modo para ``metrics.json``."""
    per_mode: dict[str, dict[str, list[Any]]] = {mode: {} for mode in MODES}
    counts: Counter[str] = Counter()
    errors: Counter[str] = Counter()

    for case_id, modes in per_case.items():  # noqa: B007 — case_id reservado para trazabilidad futura
        for mode, payload in modes.items():
            counts[mode] += 1
            if "error" in payload:
                errors[mode] += 1
                continue
            evaluation = payload["evaluation"]
            if not isinstance(evaluation, dict):
                continue
            for key, value in evaluation.items():
                if isinstance(value, (int, float)) or value is None:
                    per_mode[mode].setdefault(key, []).append(value)

    aggregated: dict[str, Any] = {}
    for mode, metrics in per_mode.items():
        aggregated[mode] = {
            "cases_total": counts[mode],
            "errors": errors[mode],
            "metrics": {
                key: {
                    "n": len(values),
                    "mean": (
                        sum(v for v in values if v is not None)
                        / max(1, sum(1 for v in values if v is not None))
                        if any(v is not None for v in values)
                        else None
                    ),
                    "min": min((v for v in values if v is not None), default=None),
                    "max": max((v for v in values if v is not None), default=None),
                }
                for key, values in metrics.items()
            },
        }

    # Métricas compuestas entre modos.
    predicted_routes = []
    expected_routes = []
    for case_id, modes in per_case.items():  # noqa: B007 — case_id reservado para trazabilidad futura
        auto = modes.get("auto")
        if auto and "evaluation" in auto and isinstance(auto["evaluation"], dict):
            evaluation = auto["evaluation"]
            resolved = evaluation.get("resolved_mode") or ""
            expected_intent = evaluation.get("expected_intent") or ""
            if resolved and expected_intent:
                predicted_routes.append(resolved)
                expected_routes.append(expected_intent)

    cm = router_confusion_matrix(
        predicted_routes=predicted_routes,
        expected_routes=expected_routes,
    )
    cm_json = {f"{expected}|{predicted}": n for (expected, predicted), n in cm.items()}

    # Empareja claim por case_id para que abstention/unjustified tengan misma longitud.
    paired: list[tuple[str, str]] = []
    for case_id, modes in per_case.items():  # noqa: B007 — case_id reservado para trazabilidad futura
        claim = modes.get("claim")
        if not claim or "evaluation" not in claim or not isinstance(claim["evaluation"], dict):
            continue
        evaluation = claim["evaluation"]
        predicted = evaluation.get("decision") or ""
        expected = ((cases_lookup.get(case_id) or {}).get("expected_output") or {}).get(
            "decisions"
        ) or {}
        expected_decision = expected.get("claim_decision") or ""
        if not predicted or not expected_decision:
            continue
        paired.append((predicted, expected_decision))

    aggregated["cross_mode"] = {
        "router_confusion_matrix": cm_json,
        "abstention": {
            "correct_rate": abstention_metrics(
                predicted_decisions=[p for p, _ in paired],
                expected_decisions=[e for _, e in paired],
            )[0]
        },
        "unjustified_resolution_rate": unjustified_resolution_rate(
            predicted_decisions=[p for p, _ in paired],
            expected_decisions=[e for _, e in paired],
        ),
        "router_cases": len(predicted_routes),
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
        lines.append(f"## {mode} ({total - errors}/{total} ok)")
        metric_blocks = block.get("metrics") or {}
        if not metric_blocks:
            lines.append("  (sin métricas)")
            continue
        for key, summary in metric_blocks.items():
            mean = summary.get("mean")
            if mean is None:
                continue
            mean_str = f"{mean:.3f}"
            n_str = str(summary["n"])
            min_str = str(summary["min"])
            max_str = str(summary["max"])
            lines.append(
                f"  - {key}: mean={mean_str} "
                f"(n={n_str}, min={min_str}, max={max_str})"
            )
    lines.append("")
    cross = metrics.get("cross_mode") or {}
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
        "--output", required=True, help="Carpeta de salida (debe estar vacía o inexistente)."
    )
    parser.add_argument("--label", default="baseline", help="Etiqueta corta de la corrida.")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    output_dir = Path(args.output).resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise SystemExit(f"Output dir {output_dir} no está vacía; bórrala o cámbiale el nombre.")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "per-case").mkdir(exist_ok=True)

    modes = tuple(m for m in args.modes.split(",") if m in MODES)
    if not modes:
        raise SystemExit(f"--modes debe contener al menos uno de {MODES}")

    cases = _load_golden(args.limit)
    print(
        f"[baseline] {len(cases)} casos, modos={modes}, concurrency={args.concurrency}, "
        f"base_url={args.base_url}",
        flush=True,
    )

    started_at = datetime.now(UTC)
    wall_start = time.monotonic()
    raw_results = asyncio.run(
        _run_all(
            cases=cases,
            modes=modes,
            concurrency=args.concurrency,
            base_url=args.base_url,
        )
    )
    duration_s = time.monotonic() - wall_start

    per_case: dict[str, dict[str, dict[str, Any]]] = {}
    for case_id, mode, payload, elapsed_s in raw_results:
        per_case.setdefault(case_id, {})[mode] = {**payload, "elapsed_s": elapsed_s}

    metrics = _aggregate(per_case, {c.get("metadata", {}).get("case_id"): c for c in cases})

    # Persistencia
    commit = _git_commit()
    manifest = {
        "label": args.label,
        "started_at": started_at.isoformat(),
        "duration_s": duration_s,
        "commit": commit,
        "golden_path": str(GOLDEN_PATH),
        "case_count": len(cases),
        "modes": list(modes),
        "concurrency": args.concurrency,
        "base_url": args.base_url,
        "models": {
            "answer": os.environ.get("OPENAI_ANSWER_MODEL", "<unset>"),
            "extraction": os.environ.get("OPENAI_CLAIM_EXTRACTION_MODEL", "<unset>"),
            "router": os.environ.get("ALLIANZ_ROUTER_MODEL", "<unset>"),
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    summary = _write_summary(
        metrics,
        cases_total=len(cases),
        modes=modes,
        label=args.label,
        duration_s=duration_s,
    )
    (output_dir / "summary.txt").write_text(summary, encoding="utf-8")

    for case_id, modes_payload in per_case.items():
        (output_dir / "per-case" / f"{case_id}.json").write_text(
            json.dumps(modes_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print(f"[baseline] ok en {duration_s:.1f}s — {output_dir}", flush=True)
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
