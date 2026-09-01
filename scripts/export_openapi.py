"""Regenerate ``docs/api/openapi.json`` from the live FastAPI app.

Run from the project root:

    uv run --project backend python scripts/export_openapi.py

The script composes the app with three in-process fake ports so the
envelope, question, claim, and resolve routes are mounted without
touching any external service. The resulting ``app.openapi()`` dict is
written to ``docs/api/openapi.json`` with stable key ordering so
subsequent diffs are easy to review.

The companion ``scripts/check_openapi.py`` (called from
``make openapi-check``) reads the same dict and fails if the file is
out of date. CI can rely on the check rather than re-running the
export on every test.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


class _FakePort:
    async def execute(self, *_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise NotImplementedError


def main() -> int:
    # Adjust sys.path so ``backend`` package imports resolve when this
    # script is invoked from the project root.
    repo_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(repo_root / "backend" / "src"))

    from infrastructure.adapters.inbound.api.app import create_app

    app = create_app(
        answer_question=_FakePort(),
        analyze_claim=_FakePort(),
        resolve_query=_FakePort(),
        allowed_profiles=("baseline", "structured"),
    )

    schema = app.openapi()
    output_path = repo_root / "docs" / "api" / "openapi.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())