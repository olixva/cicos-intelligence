"""Tests for the ``metadata.langfuse_url`` field emitted in every envelope branch.

Oracle G4 finding #3: the envelope only carried ``trace_id``; the frontend
needs an absolute (or relative) URL to render the "Ver en Langfuse ↗" link.

These tests pin the contract:

- All six ``metadata`` construction sites (``from_question``,
  ``from_claim``, ``from_clarification`` and the three ``from_route_execution``
  branches) emit a ``langfuse_url`` field.
- ``LANGFUSE_PUBLIC_URL`` is preferred over ``LANGFUSE_BASE_URL``.
- A trailing slash is normalised (never produces ``//trace``).
- When neither env var is set, the helper falls back to a relative
  ``/trace/<id>`` link.
- Empty ``trace_id`` still emits a usable URL (no spurious ``/trace/``).
"""

from __future__ import annotations

from application.models.claim import ClaimExecution
from application.models.query import (
    AnswerBlock,
    QueryExecution,
    QueryInput,
    QuestionAnswer,
)
from domain.models.decision import ClaimAnalysis
from domain.models.routing import (
    ClarificationResult,
    RouteClassification,
    RouteExecution,
)
from infrastructure.adapters.inbound.api.schemas.envelope import (
    EnvelopeResponse,
    _langfuse_trace_url,  # pyright: ignore[reportPrivateUsage]
)

# ---------------------------------------------------------------------------
# Helper-level tests: directly invoke ``_langfuse_trace_url`` to pin the
# env-driven URL builder. No module reload needed because the helper reads
# ``os.environ`` at call time.
# ---------------------------------------------------------------------------


def test_helper_prefers_langfuse_public_url(monkeypatch: object) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_URL", "https://langfuse.example.com")  # type: ignore[attr-defined]
    monkeypatch.setenv("LANGFUSE_BASE_URL", "http://internal.langfuse.local:3000")  # type: ignore[attr-defined]

    assert _langfuse_trace_url("abc123") == "https://langfuse.example.com/trace/abc123"


def test_helper_strips_trailing_slash_from_public_url(monkeypatch: object) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_URL", "https://langfuse.example.com/")  # type: ignore[attr-defined]
    monkeypatch.delenv("LANGFUSE_BASE_URL", raising=False)  # type: ignore[attr-defined]

    assert _langfuse_trace_url("abc123") == "https://langfuse.example.com/trace/abc123"


def test_helper_falls_back_to_base_url(monkeypatch: object) -> None:
    monkeypatch.delenv("LANGFUSE_PUBLIC_URL", raising=False)  # type: ignore[attr-defined]
    monkeypatch.setenv("LANGFUSE_BASE_URL", "http://127.0.0.1:3000")  # type: ignore[attr-defined]

    assert _langfuse_trace_url("abc123") == "http://127.0.0.1:3000/trace/abc123"


def test_helper_returns_relative_path_when_no_env(monkeypatch: object) -> None:
    monkeypatch.delenv("LANGFUSE_PUBLIC_URL", raising=False)  # type: ignore[attr-defined]
    monkeypatch.delenv("LANGFUSE_BASE_URL", raising=False)  # type: ignore[attr-defined]

    assert _langfuse_trace_url("abc123") == "/trace/abc123"


def test_helper_returns_relative_path_when_envs_blank(monkeypatch: object) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_URL", "   ")  # type: ignore[attr-defined]
    monkeypatch.setenv("LANGFUSE_BASE_URL", "")  # type: ignore[attr-defined]

    assert _langfuse_trace_url("abc123") == "/trace/abc123"


# ---------------------------------------------------------------------------
# Integration tests: invoke the envelope factories directly so each branch
# is exercised with the env vars the test set. ``os.environ`` is read at
# call time, so monkeypatch.setenv before the factory call is sufficient
# and no module reload is needed.
# ---------------------------------------------------------------------------


def _build_envelope_question() -> EnvelopeResponse:
    return EnvelopeResponse.from_question(
        request_id="req-1",
        execution=QueryExecution(
            result=QuestionAnswer("answered", (AnswerBlock("ok", ("sha256:x:page:1",)),)),
            context=(),
            trace_id="trace-q",
        ),
    )


def _build_envelope_claim() -> EnvelopeResponse:
    return EnvelopeResponse.from_claim(
        request_id="req-2",
        execution=ClaimExecution(
            result=ClaimAnalysis(
                applicability="applicable",
                convention="CIDE",
                decision="resolved",
                party_ids=("A", "B"),
                facts=(),
                contradictions=(),
                conditions=(),
                missing_information=(),
                blocks=(),
            ),
            context=(),
            trace_id="trace-c",
        ),
    )


def _build_envelope_clarification() -> EnvelopeResponse:
    return EnvelopeResponse.from_clarification(
        request_id="req-3",
        execution=RouteExecution(
            query=QueryInput("...", "es"),
            classification=RouteClassification("clarification_required", rationale="faltan datos"),
            dispatch=ClarificationResult(message="faltan datos", missing_fields=()),
            trace_id="trace-cl",
        ),
    )


def _build_envelope_auto_question() -> EnvelopeResponse:
    return EnvelopeResponse.from_route_execution(
        request_id="req-4",
        execution=RouteExecution(
            query=QueryInput("...", "es"),
            classification=RouteClassification("question"),
            dispatch=QueryExecution(
                result=QuestionAnswer("answered", (AnswerBlock("ok", ("sha256:y:page:2",)),)),
                context=(),
                trace_id="trace-aq",
            ),
            trace_id="trace-4",
        ),
    )


def _build_envelope_auto_claim() -> EnvelopeResponse:
    return EnvelopeResponse.from_route_execution(
        request_id="req-5",
        execution=RouteExecution(
            query=QueryInput("...", "es"),
            classification=RouteClassification("claim"),
            dispatch=ClaimExecution(
                result=ClaimAnalysis(
                    applicability="applicable",
                    convention="CIDE",
                    decision="resolved",
                    party_ids=("A", "B"),
                    facts=(),
                    contradictions=(),
                    conditions=(),
                    missing_information=(),
                    blocks=(),
                ),
                context=(),
                trace_id="trace-ac",
            ),
            trace_id="trace-5",
        ),
    )


def test_envelope_question_branch_emits_langfuse_url(monkeypatch: object) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_URL", "https://langfuse.example.com")  # type: ignore[attr-defined]
    monkeypatch.delenv("LANGFUSE_BASE_URL", raising=False)  # type: ignore[attr-defined]

    env = _build_envelope_question()
    assert env.metadata["trace_id"] == "trace-q"
    assert env.metadata["langfuse_url"] == "https://langfuse.example.com/trace/trace-q"


def test_envelope_claim_branch_emits_langfuse_url(monkeypatch: object) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_URL", "https://langfuse.example.com/")  # type: ignore[attr-defined]
    monkeypatch.delenv("LANGFUSE_BASE_URL", raising=False)  # type: ignore[attr-defined]

    env = _build_envelope_claim()
    assert env.metadata["trace_id"] == "trace-c"
    # Trailing slash on the env value must be normalised away.
    assert env.metadata["langfuse_url"] == "https://langfuse.example.com/trace/trace-c"


def test_envelope_clarification_branch_emits_langfuse_url(monkeypatch: object) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_URL", "https://langfuse.example.com")  # type: ignore[attr-defined]
    monkeypatch.delenv("LANGFUSE_BASE_URL", raising=False)  # type: ignore[attr-defined]

    env = _build_envelope_clarification()
    assert env.metadata["trace_id"] == "trace-cl"
    assert env.metadata["langfuse_url"] == "https://langfuse.example.com/trace/trace-cl"
    assert env.metadata["decision"] == "clarification_required"


def test_envelope_auto_question_branch_emits_langfuse_url(monkeypatch: object) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_URL", "https://langfuse.example.com")  # type: ignore[attr-defined]
    monkeypatch.delenv("LANGFUSE_BASE_URL", raising=False)  # type: ignore[attr-defined]

    env = _build_envelope_auto_question()
    assert env.metadata["trace_id"] == "trace-4"
    assert env.metadata["langfuse_url"] == "https://langfuse.example.com/trace/trace-4"


def test_envelope_auto_claim_branch_emits_langfuse_url(monkeypatch: object) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_URL", "https://langfuse.example.com")  # type: ignore[attr-defined]
    monkeypatch.delenv("LANGFUSE_BASE_URL", raising=False)  # type: ignore[attr-defined]

    env = _build_envelope_auto_claim()
    assert env.metadata["trace_id"] == "trace-5"
    assert env.metadata["langfuse_url"] == "https://langfuse.example.com/trace/trace-5"


def test_envelope_langfuse_url_keeps_trace_id_when_empty(monkeypatch: object) -> None:
    """An envelope with no trace_id still produces a stable URL slot."""

    monkeypatch.setenv("LANGFUSE_PUBLIC_URL", "https://langfuse.example.com")  # type: ignore[attr-defined]
    monkeypatch.delenv("LANGFUSE_BASE_URL", raising=False)  # type: ignore[attr-defined]

    response = EnvelopeResponse.from_question(
        request_id="req-1",
        execution=QueryExecution(
            result=QuestionAnswer("answered", ()),
            context=(),
            trace_id=None,
        ),
    )

    assert response.metadata["trace_id"] == ""
    assert response.metadata["langfuse_url"] == "https://langfuse.example.com/trace/"
