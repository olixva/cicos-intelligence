"""Public, credential-free model configuration used by live evaluation runners."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any, cast


def evaluation_runtime_configuration(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return the effective model/guard settings without exposing credentials."""

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
    }


def assert_evaluation_runtime_matches(
    expected: Mapping[str, Any], actual: Mapping[str, Any]
) -> None:
    """Fail before a campaign if the live API differs from its runner environment."""

    def compare(path: str, expected_value: Any, actual_value: Any) -> None:
        if isinstance(expected_value, Mapping) and isinstance(actual_value, Mapping):
            expected_mapping = cast(Mapping[str, Any], expected_value)
            actual_mapping = cast(Mapping[str, Any], actual_value)
            keys: set[str] = set(expected_mapping) | set(actual_mapping)
            for key in sorted(keys):
                if key not in expected_mapping or key not in actual_mapping:
                    raise RuntimeError(f"backend configuration mismatch at {path}.{key}")
                compare(f"{path}.{key}", expected_mapping[key], actual_mapping[key])
            return
        if expected_value != actual_value:
            raise RuntimeError(
                f"backend configuration mismatch at {path}: "
                f"expected {expected_value!r}, got {actual_value!r}"
            )

    compare("configuration", expected, actual)
