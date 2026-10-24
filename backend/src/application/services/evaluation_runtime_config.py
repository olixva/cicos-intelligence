"""Safe runtime configuration and provenance for evaluation runs."""

from __future__ import annotations

import hashlib
import os
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from infrastructure.config.rules_artifacts import DEFAULT_DOCUMENT_HASH


def _unit_float(environment: Mapping[str, str], name: str, default: float) -> float:
    try:
        value = float(environment.get(name, str(default)))
    except ValueError as error:
        raise ValueError(f"{name} must be a number between 0 and 1") from error
    if not 0 <= value <= 1:
        raise ValueError(f"{name} must be a number between 0 and 1")
    return value


def _git_commit(repo_root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except OSError, subprocess.CalledProcessError:
        return "unknown"


def evaluation_build_fingerprint(repo_root: Path) -> str:
    """Hash source, scripts and runtime configuration as they exist on disk."""
    digest = hashlib.sha256()
    roots = ("backend/src", "backend/scripts", "configs", "prompts")
    files = sorted(
        path
        for relative_root in roots
        for path in (repo_root / relative_root).rglob("*")
        if path.is_file()
        and not path.is_symlink()
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
    )
    for path in files:
        relative = path.relative_to(repo_root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        try:
            digest.update(path.read_bytes())
        except OSError:
            digest.update(b"<unreadable>")
        digest.update(b"\0")
    return digest.hexdigest()


def evaluation_runtime_configuration(
    environ: Mapping[str, str] | None = None,
    *,
    repo_root: Path | None = None,
    active_index_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve effective provider settings without exposing any credential."""
    environment = os.environ if environ is None else environ
    router_backend = environment.get("ALLIANZ_ROUTER_BACKEND", "jev").strip().lower()
    if router_backend not in {"openai", "jev"}:
        raise ValueError("ALLIANZ_ROUTER_BACKEND must be 'openai' or 'jev'")
    router_model = (
        environment.get("TYPESAFE_DEFAULT_MODEL", "jev-latest")
        if router_backend == "jev"
        else environment.get("ALLIANZ_ROUTER_MODEL", "gpt-6-luna")
    )
    guard_backend = environment.get("ALLIANZ_INPUT_GUARD", "jev").strip().lower()
    if guard_backend not in {"off", "jev"}:
        raise ValueError("ALLIANZ_INPUT_GUARD must be 'off' or 'jev'")
    router = {
        "backend": router_backend,
        "model": router_model,
        "min_confidence": (
            _unit_float(environment, "ALLIANZ_JEV_ROUTER_MIN_CONFIDENCE", 0.4)
            if router_backend == "jev"
            else None
        ),
    }
    input_guard = {
        "backend": guard_backend,
        "injection_threshold": _unit_float(environment, "ALLIANZ_JEV_GUARD_INJECTION", 0.9),
        "off_topic_threshold": _unit_float(environment, "ALLIANZ_JEV_GUARD_OFF_TOPIC", 0.95),
    }
    models = {
        "answer": environment.get("OPENAI_ANSWER_MODEL", "gpt-6.1-sol"),
        "extraction": environment.get("OPENAI_CLAIM_EXTRACTION_MODEL", "gpt-6.1-sol"),
        "router": router_model,
    }
    root = repo_root or Path(__file__).resolve().parents[4]
    commit = environment.get("ALLIANZ_BUILD_COMMIT") or _git_commit(root)
    fingerprint = environment.get("ALLIANZ_BUILD_FINGERPRINT") or evaluation_build_fingerprint(root)
    provenance: dict[str, Any] = {
        "commit": commit,
        "build_fingerprint": fingerprint,
        "document_hash": environment.get("ALLIANZ_DOCUMENT_HASH", DEFAULT_DOCUMENT_HASH),
        "active_index_identity": (
            None if active_index_identity is None else dict(active_index_identity)
        ),
    }
    return {
        "router": router,
        "input_guard": input_guard,
        "models": models,
        "provenance": provenance,
    }


def assert_evaluation_runtime_matches(
    expected: Mapping[str, Any],
    actual: Mapping[str, Any],
    *,
    require_active_index_identity: bool = False,
) -> None:
    """Reject a comparison when provider/model or build inputs differ."""
    for section in ("router", "input_guard", "models"):
        _assert_mapping_matches(expected.get(section), actual.get(section), section)
    expected_provenance_raw = expected.get("provenance")
    actual_provenance_raw = actual.get("provenance")
    expected_provenance = (
        cast(Mapping[str, Any], expected_provenance_raw)
        if isinstance(expected_provenance_raw, Mapping)
        else None
    )
    actual_provenance = (
        cast(Mapping[str, Any], actual_provenance_raw)
        if isinstance(actual_provenance_raw, Mapping)
        else None
    )
    if isinstance(expected_provenance, Mapping) and isinstance(actual_provenance, Mapping):
        for field in ("commit", "build_fingerprint", "document_hash"):
            if field in expected_provenance and expected_provenance[field] != actual_provenance.get(
                field
            ):
                raise RuntimeError(
                    f"evaluation backend configuration mismatch at provenance.{field}"
                )
        expected_identity_raw = expected_provenance.get("active_index_identity")
        actual_identity_raw = actual_provenance.get("active_index_identity")
        expected_identity = (
            cast(Mapping[str, Any], expected_identity_raw)
            if isinstance(expected_identity_raw, Mapping)
            else None
        )
        actual_identity = (
            cast(Mapping[str, Any], actual_identity_raw)
            if isinstance(actual_identity_raw, Mapping)
            else None
        )
        if require_active_index_identity and actual_identity is None:
            raise RuntimeError(
                "evaluation backend configuration mismatch at provenance.active_index_identity"
            )
        if actual_identity is not None:
            alias_name = actual_identity.get("alias_name")
            collection_name = actual_identity.get("collection_name")
            points_count = actual_identity.get("points_count")
            signature_raw = actual_identity.get("index_signature")
            signature = (
                cast(Mapping[str, Any], signature_raw)
                if isinstance(signature_raw, Mapping)
                else None
            )
            if (
                alias_name != "allianz-manual-active"
                or not isinstance(collection_name, str)
                or not collection_name
                or type(points_count) is not int
                or points_count <= 0
                or signature is None
            ):
                raise RuntimeError(
                    "evaluation backend configuration mismatch at provenance.active_index_identity"
                )
            actual_hash = signature.get("document_hash")
            expected_hash = expected_provenance.get("document_hash")
            if actual_hash != expected_hash:
                raise RuntimeError(
                    "evaluation backend configuration mismatch at provenance.active_index_identity"
                )
            if expected_identity is not None:
                _assert_mapping_matches(
                    expected_identity,
                    actual_identity,
                    "provenance.active_index_identity",
                )
        elif expected_identity is not None:
            raise RuntimeError(
                "evaluation backend configuration mismatch at provenance.active_index_identity"
            )


def pin_active_index_identity(
    expected: Mapping[str, Any], actual: Mapping[str, Any]
) -> dict[str, Any]:
    """Bind the live alias signature into a campaign identity after preflight."""
    assert_evaluation_runtime_matches(expected, actual, require_active_index_identity=True)
    expected_provenance_raw = expected.get("provenance")
    actual_provenance_raw = actual.get("provenance")
    if not isinstance(expected_provenance_raw, Mapping) or not isinstance(
        actual_provenance_raw, Mapping
    ):
        raise RuntimeError("evaluation backend configuration mismatch at provenance")
    expected_provenance = cast(Mapping[str, Any], expected_provenance_raw)
    actual_provenance = cast(Mapping[str, Any], actual_provenance_raw)
    actual_identity = actual_provenance.get("active_index_identity")
    if not isinstance(actual_identity, Mapping):
        raise RuntimeError(
            "evaluation backend configuration mismatch at provenance.active_index_identity"
        )
    active_identity = cast(Mapping[str, Any], actual_identity)
    return {
        **expected,
        "provenance": {
            **expected_provenance,
            "active_index_identity": dict(active_identity),
        },
    }


def _assert_mapping_matches(expected: object, actual: object, prefix: str) -> None:
    if not isinstance(expected, Mapping):
        return
    if not isinstance(actual, Mapping):
        raise RuntimeError(f"evaluation backend configuration mismatch at {prefix}")
    expected_mapping = cast(Mapping[str, Any], expected)
    actual_mapping = cast(Mapping[str, Any], actual)
    for key, expected_value in expected_mapping.items():
        if isinstance(expected_value, Mapping):
            _assert_mapping_matches(
                cast(Mapping[str, Any], expected_value),
                actual_mapping.get(key),
                f"{prefix}.{key}",
            )
        elif expected_value != actual_mapping.get(key):
            raise RuntimeError(f"evaluation backend configuration mismatch at {prefix}.{key}")
