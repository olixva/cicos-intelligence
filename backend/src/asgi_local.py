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
from dataclasses import asdict
from typing import cast

from bootstrap import build_api

_ACTIVE_ALIAS = "allianz-manual-active"


def _qdrant_active_index_identity() -> dict[str, object] | None:
    """Resolve the active alias to its collection and signed index metadata.

    Network, parsing and signature errors yield ``None``. The health route
    then exposes missing provenance, and ``/health/ready`` remains not ready.
    """

    from infrastructure.adapters.outbound.retriever.qdrant_retriever import (
        InvalidIndexDataError,
        signature_from_metadata,
    )

    qdrant_url = (
        os.environ.get("QDRANT_URL")
        or os.environ.get("ALLIANZ_QDRANT_URL")
        or "http://127.0.0.1:6333"
    ).rstrip("/")
    try:
        with urllib.request.urlopen(f"{qdrant_url}/aliases", timeout=2) as response:
            payload = json.loads(response.read())
    except urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError:
        return None

    if not isinstance(payload, dict):
        return None
    payload_data = cast(dict[str, object], payload)
    result_raw = payload_data.get("result", {})
    result = cast(dict[str, object], result_raw) if isinstance(result_raw, dict) else {}
    aliases = result.get("aliases", [])
    if not isinstance(aliases, list):
        return None
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
        return None

    target = active.get("collection_name")
    if not isinstance(target, str) or not target:
        return None

    try:
        with urllib.request.urlopen(f"{qdrant_url}/collections/{target}", timeout=2) as response:
            details = json.loads(response.read())
    except urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError:
        return None

    if not isinstance(details, dict):
        return None
    details_data = cast(dict[str, object], details)
    details_result_raw = details_data.get("result", {})
    details_result = (
        cast(dict[str, object], details_result_raw) if isinstance(details_result_raw, dict) else {}
    )
    points_count = details_result.get("points_count", 0)
    config_raw = details_result.get("config")
    config = cast(dict[str, object], config_raw) if isinstance(config_raw, dict) else {}
    metadata_raw = config.get("metadata")
    metadata = cast(dict[str, object], metadata_raw) if isinstance(metadata_raw, dict) else None
    if type(points_count) is not int or points_count <= 0 or metadata is None:
        return None
    try:
        signature = signature_from_metadata(metadata)
    except InvalidIndexDataError, ValueError:
        return None
    return {
        "alias_name": _ACTIVE_ALIAS,
        "collection_name": target,
        "points_count": points_count,
        "index_signature": asdict(signature),
    }


def _qdrant_alias_is_published() -> bool:
    """Return True iff the active alias resolves to a signed, non-empty index."""

    return _qdrant_active_index_identity() is not None


def app():
    """Return the local FastAPI app with the ``baseline`` profile and a real ready probe."""

    return build_api(
        profile_name="baseline",
        required_index_ready=_qdrant_alias_is_published,
        active_index_identity=_qdrant_active_index_identity,
    )
