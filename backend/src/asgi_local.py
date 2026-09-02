"""ASGI factory entry point for local end-to-end testing.

uvicorn's ``--factory`` flag invokes the importable callable with no
arguments, which leaves every profile kwarg at ``None``. Without any
profile, every workflow factory short-circuits to ``None`` and
``build_api`` raises the aggregate-fail ``RuntimeError``. This module
exposes the factory with the local ``baseline`` profile wired in and a
real Qdrant probe so ``/health/ready`` reflects the actual state of
the active alias (``allianz-manual-active``).

The return type is intentionally unannotated: ``build_api.__annotations__["return"]``
contains the literal token ``"return"`` which is not a valid identifier
in a type hint. Letting pyright infer ``FastAPI`` from the implementation
keeps the surface simple.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from bootstrap import build_api

_ACTIVE_ALIAS = "allianz-manual-active"


def _qdrant_alias_is_published() -> bool:
    """Return True iff the local Qdrant exposes a non-empty collection behind the active alias.

    The probe is a single GET against ``/aliases`` plus a follow-up
    ``/collections/{name}`` only when the alias resolves. We treat any
    network or parsing error as "not ready" so the frontend sees a
    consistent 503 instead of a 500 when Qdrant is down.
    """

    qdrant_url = os.environ.get("ALLIANZ_QDRANT_URL", "http://127.0.0.1:6333").rstrip("/")
    try:
        with urllib.request.urlopen(f"{qdrant_url}/aliases", timeout=2) as response:
            payload = json.loads(response.read())
    except urllib.error.URLError, TimeoutError, json.JSONDecodeError:
        return False

    aliases = payload.get("result", {}).get("aliases", []) if isinstance(payload, dict) else []
    active = next(
        (alias for alias in aliases if alias.get("alias_name") == _ACTIVE_ALIAS),
        None,
    )
    if active is None:
        return False

    target = active.get("collection_name")
    if not isinstance(target, str) or not target:
        return False

    try:
        with urllib.request.urlopen(f"{qdrant_url}/collections/{target}", timeout=2) as response:
            details = json.loads(response.read())
    except urllib.error.URLError, TimeoutError, json.JSONDecodeError:
        return False

    points_count = (
        details.get("result", {}).get("points_count", 0) if isinstance(details, dict) else 0
    )
    return isinstance(points_count, int) and points_count > 0


def app():
    """Return the local FastAPI app with the ``baseline`` profile and a real ready probe."""

    return build_api(
        profile_name="baseline",
        required_index_ready=_qdrant_alias_is_published,
    )
