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
