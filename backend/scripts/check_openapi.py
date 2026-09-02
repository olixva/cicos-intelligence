"""Fail if ``docs/api/openapi.json`` is stale.

Run from the project root:

    uv run --project backend python backend/scripts/check_openapi.py

Composes the app the same way ``export_openapi.py`` does and compares
the regenerated schema to the committed JSON file. CI should run this
on every PR; if the file is out of date the command exits non-zero so
the developer regenerates it and commits the diff.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
OPENAPI_PATH = REPOSITORY_ROOT / "docs" / "api" / "openapi.json"


class _FakePort:
    async def execute(self, *_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise NotImplementedError


def main() -> int:
    sys.path.insert(0, str(REPOSITORY_ROOT / "backend" / "src"))

    from infrastructure.adapters.inbound.api.app import create_app

    app = create_app(
        answer_question=_FakePort(),
        analyze_claim=_FakePort(),
        resolve_query=_FakePort(),
        allowed_profiles=("baseline", "structured"),
    )

    expected = app.openapi()
    if not OPENAPI_PATH.exists():
        print(f"missing {OPENAPI_PATH}", file=sys.stderr)
        return 1

    actual = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    if actual != expected:
        diff_start = next(
            (key for key in expected if expected.get(key) != actual.get(key)),
            None,
        )
        print(
            f"openapi.json is out of date (first diverging key: {diff_start!r}); "
            "run backend/scripts/export_openapi.py and commit the result.",
            file=sys.stderr,
        )
        return 1
    print("openapi.json is up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
