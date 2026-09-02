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
from typing import cast

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

    if not isinstance(payload, dict):
        return False
    payload_data = cast(dict[str, object], payload)
    result_raw = payload_data.get("result", {})
    result = cast(dict[str, object], result_raw) if isinstance(result_raw, dict) else {}
    aliases = result.get("aliases", [])
    if not isinstance(aliases, list):
        return False
    alias_entries = cast(list[object], aliases)
    active: dict[str, object] | None = None
    for raw_alias in alias_entries:
        if not isinstance(raw_alias, dict):
            continue
        alias = cast(dict[str, object], raw_alias)
        if alias.get("alias_name") == _ACTIVE_ALIAS:
            active = alias
            break
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

    if not isinstance(details, dict):
        return False
    details_data = cast(dict[str, object], details)
    details_result_raw = details_data.get("result", {})
    details_result = (
        cast(dict[str, object], details_result_raw) if isinstance(details_result_raw, dict) else {}
    )
    points_count = details_result.get("points_count", 0)
    return isinstance(points_count, int) and points_count > 0


def app():
    """Return the local FastAPI app with the ``baseline`` profile and a real ready probe."""

    return build_api(
        profile_name="baseline",
        required_index_ready=_qdrant_alias_is_published,
    )
