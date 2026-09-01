"""Bootstrap-level wiring for ``build_api`` partial-failure behavior.

These tests pin the contract that ``build_api`` keeps mounting the surviving
port when one factory raises, surfaces the skip through the module logger
rather than ``sys.stderr``, and aggregates total failure into a hard
``RuntimeError``.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from application.models.query import QueryExecution, QueryInput, QuestionAnswer


@dataclass
class _StubAnswerQuestion:
    """Minimum-viable question port so the question router still mounts."""

    async def execute(self, query: QueryInput) -> QueryExecution:
        return QueryExecution(result=QuestionAnswer("answered", ()), context=(), trace_id="t")


def _raise_miss(profile: str) -> None:
    raise ValueError("simulated miss")


def test_build_api_keeps_surviving_port_and_logs_skip(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A failing claim factory must not prevent the question router from mounting."""

    import bootstrap

    monkeypatch.setattr(bootstrap, "build_answer_question", lambda profile: _StubAnswerQuestion())
    monkeypatch.setattr(bootstrap, "build_analyze_claim", _raise_miss)

    with caplog.at_level("WARNING", logger="bootstrap"):
        app = bootstrap.build_api(question_profile="q", claim_profile="c")

    client = TestClient(app)
    assert client.post("/api/v1/questions/answer", json={"text": "x"}).status_code == 200
    assert client.post("/api/v1/claims/analyze", json={"text": "y"}).status_code == 404
    assert any(
        "build_api: skipping analyze_claim port" in record.message
        and "simulated miss" in record.message
        for record in caplog.records
    )


def test_build_api_raises_runtime_error_when_every_port_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both factories failing must surface the existing aggregate RuntimeError."""

    import bootstrap

    monkeypatch.setattr(bootstrap, "build_answer_question", _raise_miss)
    monkeypatch.setattr(bootstrap, "build_analyze_claim", _raise_miss)

    with pytest.raises(
        RuntimeError, match=r"build_api\(\) could not compose any workflow port"
    ):
        bootstrap.build_api(question_profile="q", claim_profile="c")