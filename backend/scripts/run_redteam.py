"""Red-team runner: lanza ``data/evaluation/redteam/cases.jsonl`` contra el backend.

Uso::

    # Backend levantado en 127.0.0.1:8000 (make serve-backend).
    cd backend && uv run --no-sync python scripts/run_redteam.py \\
        --output ../data/evaluation/results/redteam-$(date +%F)

Cada caso declara su criterio de vulneración (canario, fragmento del prompt
interno, cita fuera del manual, estado o decisión prohibidos); no hay juez LLM.
Resultados: ``manifest.json``, ``metrics.json``, ``summary.txt`` y
``per-case/<case_id>.json``. Sale con código 1 si algún ataque tiene éxito.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

_BACKEND_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(_BACKEND_SRC))

from infrastructure.adapters.outbound.evaluation.redteam import (  # noqa: E402
    RedTeamCase,
    RedTeamVerdict,
    evaluate_http_status,
    evaluate_response,
    load_cases,
    summarize,
)

CASES_PATH = Path(__file__).resolve().parents[2] / "data/evaluation/redteam/cases.jsonl"
DEFAULT_BASE_URL = os.environ.get("ALLIANZ_BASELINE_URL", "http://127.0.0.1:8000")
DOCUMENT_HASH = os.environ.get(
    "ALLIANZ_DOCUMENT_HASH", "b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344"
)
PAGE_COUNT = int(os.environ.get("ALLIANZ_MANUAL_PAGES", "111"))
TIMEOUT_S = 180.0


async def _run_one(
    client: httpx.AsyncClient, semaphore: asyncio.Semaphore, case: RedTeamCase
) -> tuple[RedTeamCase, RedTeamVerdict, dict[str, Any]]:
    payload = {
        "text": case.text,
        "language": case.language,
        "mode": case.mode,
        "session_id": f"redteam-{case.case_id}",
    }
    try:
        async with semaphore:
            response = await client.post("/api/v1/queries", json=payload)
    except httpx.HTTPError as error:
        return case, RedTeamVerdict("fail", "error", (repr(error),)), {"error": repr(error)}
    if response.status_code != 200:
        verdict = evaluate_http_status(case, response.status_code)
        return case, verdict, {"status_code": response.status_code, "body": response.text[:500]}
    body = response.json()
    verdict = evaluate_response(case, body, document_hash=DOCUMENT_HASH, page_count=PAGE_COUNT)
    return case, verdict, {"status_code": 200, "response": body}


async def _run_all(
    cases: list[RedTeamCase], concurrency: int, base_url: str
) -> list[tuple[RedTeamCase, RedTeamVerdict, dict[str, Any]]]:
    semaphore = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient(base_url=base_url, timeout=TIMEOUT_S) as client:
        ready = await client.get("/health/ready")
        ready.raise_for_status()
        return await asyncio.gather(*(_run_one(client, semaphore, case) for case in cases))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"{args.output} ya existe; usa otra carpeta de salida")

    cases = load_cases(CASES_PATH.read_text(encoding="utf-8").splitlines())
    started = datetime.now(UTC)
    results = asyncio.run(_run_all(cases, args.concurrency, args.base_url))
    metrics = summarize([(case, verdict) for case, verdict, _ in results])

    (args.output / "per-case").mkdir(parents=True)
    for case, verdict, raw in results:
        record = {
            "case": case.__dict__ | {"text": case.text[:300]},
            "verdict": verdict.verdict,
            "outcome": verdict.outcome,
            "reasons": list(verdict.reasons),
            "raw": raw,
        }
        (args.output / "per-case" / f"{case.case_id}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    manifest = {
        "started_at": started.isoformat(),
        "duration_s": (datetime.now(UTC) - started).total_seconds(),
        "base_url": args.base_url,
        "cases": len(cases),
        "models": {
            "answer": os.environ.get("OPENAI_ANSWER_MODEL", "<unset>"),
            "extraction": os.environ.get("OPENAI_CLAIM_EXTRACTION_MODEL", "<unset>"),
            "router": os.environ.get("ALLIANZ_ROUTER_MODEL", "<unset>"),
        },
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (args.output / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    lines = [
        f"ataques: {metrics['attack_cases']}  tasa de éxito del atacante: "
        f"{metrics['attack_success_rate']:.3f}",
        f"controles benignos: {metrics['control_cases']}  sobre-rechazo: "
        f"{metrics['over_refusal_rate']:.3f}",
        "",
    ]
    lines += [
        f"{cat:18} {b['failed']}/{b['total']} vulnerados"
        for cat, b in sorted(metrics["by_category"].items())
    ]
    failures = [(c, v) for c, v, _ in results if v.verdict == "fail"]
    lines += ["", "FALLOS:"] + [f"  {c.case_id}: {'; '.join(v.reasons)}" for c, v in failures]
    summary = "\n".join(lines)
    (args.output / "summary.txt").write_text(summary + "\n", encoding="utf-8")
    print(summary)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
