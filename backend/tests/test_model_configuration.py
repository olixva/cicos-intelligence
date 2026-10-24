"""Tests for the OpenAI model defaults used by the composition root."""

from __future__ import annotations

import pytest


def test_openai_model_defaults() -> None:
    from bootstrap import model_configuration

    assert model_configuration({}) == {
        "answer": "gpt-6.1-sol",
        "extraction": "gpt-6.1-sol",
        "router": "gpt-6-luna",
    }


def test_openai_model_environment_overrides_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    from bootstrap import model_configuration

    monkeypatch.setenv("OPENAI_ANSWER_MODEL", "answer-test-model")
    monkeypatch.setenv("OPENAI_CLAIM_EXTRACTION_MODEL", "extraction-test-model")
    monkeypatch.setenv("ALLIANZ_ROUTER_MODEL", "router-test-model")

    assert model_configuration() == {
        "answer": "answer-test-model",
        "extraction": "extraction-test-model",
        "router": "router-test-model",
    }


def test_qdrant_endpoint_resolution_uses_one_configured_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from bootstrap import _qdrant_url

    monkeypatch.delenv("QDRANT_URL", raising=False)
    monkeypatch.setenv("ALLIANZ_QDRANT_URL", "http://qdrant-custom:6333")
    assert _qdrant_url() == "http://qdrant-custom:6333"

    monkeypatch.setenv("QDRANT_URL", "http://qdrant-primary:6333")
    assert _qdrant_url() == "http://qdrant-primary:6333"


def test_local_langfuse_accepts_docker_host_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    from bootstrap import _require_local_langfuse_environment

    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-local-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "secret-local-test")
    monkeypatch.setenv("LANGFUSE_BASE_URL", "http://host.docker.internal:3000")

    _require_local_langfuse_environment()


def test_local_langfuse_rejects_remote_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    from bootstrap import _require_local_langfuse_environment

    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-local-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "secret-local-test")
    monkeypatch.setenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")

    with pytest.raises(ValueError, match="must point to the local Langfuse service"):
        _require_local_langfuse_environment()


def test_validated_jev_router_and_guard_are_the_runtime_defaults() -> None:
    from application.services.evaluation_runtime_config import evaluation_runtime_configuration

    configuration = evaluation_runtime_configuration({})

    assert configuration["router"] == {
        "backend": "jev",
        "model": "jev-latest",
        "min_confidence": 0.4,
    }
    assert configuration["input_guard"] == {
        "backend": "jev",
        "injection_threshold": 0.9,
        "off_topic_threshold": 0.95,
    }


def test_openai_router_and_disabled_guard_remain_explicit_overrides() -> None:
    from application.services.evaluation_runtime_config import evaluation_runtime_configuration

    configuration = evaluation_runtime_configuration(
        {"ALLIANZ_ROUTER_BACKEND": "openai", "ALLIANZ_INPUT_GUARD": "off"}
    )

    assert configuration["router"] == {
        "backend": "openai",
        "model": "gpt-6-luna",
        "min_confidence": None,
    }
    assert configuration["input_guard"]["backend"] == "off"


def test_evaluation_preflight_requires_the_active_signed_index() -> None:
    from application.services.evaluation_runtime_config import (
        assert_evaluation_runtime_matches,
        evaluation_runtime_configuration,
    )

    expected = evaluation_runtime_configuration({"ALLIANZ_DOCUMENT_HASH": "a" * 64})
    actual = evaluation_runtime_configuration({"ALLIANZ_DOCUMENT_HASH": "a" * 64})

    with pytest.raises(RuntimeError, match="active_index_identity"):
        assert_evaluation_runtime_matches(expected, actual, require_active_index_identity=True)


def test_evaluation_preflight_compares_the_full_active_index_signature() -> None:
    from application.services.evaluation_runtime_config import (
        assert_evaluation_runtime_matches,
        evaluation_runtime_configuration,
    )

    expected_identity = {
        "alias_name": "allianz-manual-active",
        "collection_name": "allianz-collection-v1",
        "points_count": 118,
        "index_signature": {
            "document_hash": "a" * 64,
            "embedding_model": "text-embedding-3-small",
        },
    }
    actual_identity = {
        **expected_identity,
        "index_signature": {
            "document_hash": "a" * 64,
            "embedding_model": "unexpected-embedding",
        },
    }
    expected = evaluation_runtime_configuration(
        {"ALLIANZ_DOCUMENT_HASH": "a" * 64}, active_index_identity=expected_identity
    )
    actual = evaluation_runtime_configuration(
        {"ALLIANZ_DOCUMENT_HASH": "a" * 64}, active_index_identity=actual_identity
    )

    with pytest.raises(RuntimeError, match="active_index_identity"):
        assert_evaluation_runtime_matches(expected, actual, require_active_index_identity=True)
