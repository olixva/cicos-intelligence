"""Public, credential-free model configuration used by live evaluation runners."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

DEFAULT_DOCUMENT_HASH = "b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344"


def evaluation_runtime_configuration(
    environ: Mapping[str, str] | None = None,
    *,
    active_index_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return effective settings and safe runtime provenance, never credentials."""

    environment = os.environ if environ is None else environ
    router_backend = environment.get("ALLIANZ_ROUTER_BACKEND", "jev").strip().lower()
    router_model = (
        environment.get("TYPESAFE_DEFAULT_MODEL", "jev-latest")
        if router_backend == "jev"
        else environment.get("ALLIANZ_ROUTER_MODEL", "gpt-6-luna")
    )
    guard_backend = environment.get("ALLIANZ_INPUT_GUARD", "jev").strip().lower()
    return {
        "router": {
            "backend": router_backend,
            "model": router_model,
            "min_confidence": (
                float(environment.get("ALLIANZ_JEV_ROUTER_MIN_CONFIDENCE", "0.4"))
                if router_backend == "jev"
                else None
            ),
        },
        "input_guard": {
            "backend": guard_backend,
            "injection_threshold": float(environment.get("ALLIANZ_JEV_GUARD_INJECTION", "0.9")),
            "off_topic_threshold": float(environment.get("ALLIANZ_JEV_GUARD_OFF_TOPIC", "0.95")),
        },
        "models": {
            "answer": environment.get("OPENAI_ANSWER_MODEL", "gpt-6.1-sol"),
            "extraction": environment.get("OPENAI_CLAIM_EXTRACTION_MODEL", "gpt-6.1-sol"),
        },
        "provenance": {
            "build_commit": environment.get("ALLIANZ_BUILD_COMMIT"),
            "build_fingerprint": environment.get("ALLIANZ_BUILD_FINGERPRINT"),
            "configured_document_hash": environment.get(
                "ALLIANZ_DOCUMENT_HASH", DEFAULT_DOCUMENT_HASH
            ),
            "active_index_identity": (
                None if active_index_identity is None else dict(active_index_identity)
            ),
        },
    }


def evaluation_build_fingerprint(repo_root: Path) -> str:
    """Hash tracked edits and non-ignored untracked files for this worktree."""

    try:
        tracked_diff = subprocess.check_output(
            ["git", "diff", "--binary", "HEAD", "--"], cwd=repo_root
        )
        untracked = subprocess.check_output(
            ["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=repo_root
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise RuntimeError(f"could not fingerprint build worktree at {repo_root}") from error

    digest = sha256()
    digest.update(b"tracked-diff\0")
    digest.update(tracked_diff)
    for relative_path in sorted(path for path in untracked.split(b"\0") if path):
        path = repo_root / os.fsdecode(relative_path)
        if not path.is_file():
            continue
        digest.update(b"untracked\0")
        digest.update(relative_path)
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def assert_evaluation_runtime_matches(
    expected: Mapping[str, Any], actual: Mapping[str, Any]
) -> None:
    """Require expected settings while allowing the API to report extra provenance."""

    def compare(path: str, expected_value: Any, actual_value: Any) -> None:
        if isinstance(expected_value, Mapping) and isinstance(actual_value, Mapping):
            expected_mapping = cast(Mapping[str, Any], expected_value)
            actual_mapping = cast(Mapping[str, Any], actual_value)
            for key in sorted(expected_mapping):
                if key not in actual_mapping:
                    raise RuntimeError(f"backend configuration mismatch at {path}.{key}")
                compare(f"{path}.{key}", expected_mapping[key], actual_mapping[key])
            return
        if expected_value != actual_value:
            raise RuntimeError(
                f"backend configuration mismatch at {path}: "
                f"expected {expected_value!r}, got {actual_value!r}"
            )

    compare("configuration", expected, actual)
