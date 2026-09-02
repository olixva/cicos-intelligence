"""Tests for the ``metadata.langfuse_url`` field emitted in every envelope branch.

Oracle G4 finding #3: the envelope only carried ``trace_id``; the frontend
needs an absolute (or relative) URL to render the "Ver en Langfuse ↗" link.

These tests pin the contract:

- All six ``metadata`` construction sites (``from_question``,
  ``from_claim``, ``from_clarification`` and the three ``from_route_execution``
  branches) emit a ``langfuse_url`` field.
- ``LANGFUSE_PUBLIC_URL`` is preferred over ``LANGFUSE_BASE_URL``.
- A trailing slash is normalised.
- The URL uses Langfuse's real route, ``/project/<pid>/traces/<tid>``. The
  old ``/trace/<id>`` shape is not a route and sent users to "trace not
  found", so it must never be emitted again.
- When the project id, the base URL or the trace id is missing, the helper
  returns ``None`` rather than a link that is known to 404.
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
from domain.models.rule_evaluation import RuleEvaluation
from infrastructure.adapters.inbound.api.schemas.envelope import (
    EnvelopeResponse,
    _langfuse_trace_url,  # pyright: ignore[reportPrivateUsage]
)

# ---------------------------------------------------------------------------
# Helper-level tests: directly invoke ``_langfuse_trace_url`` to pin the
# env-driven URL builder. No module reload needed because the helper reads
# ``os.environ`` at call time.
# ---------------------------------------------------------------------------


def test_helper_builds_the_real_langfuse_route(monkeypatch: object) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_URL", "https://langfuse.example.com")  # type: ignore[attr-defined]
    monkeypatch.setenv("LANGFUSE_BASE_URL", "http://internal.langfuse.local:3000")  # type: ignore[attr-defined]
    monkeypatch.setenv("LANGFUSE_PROJECT_ID", "allianz-rag")  # type: ignore[attr-defined]

    assert (
        _langfuse_trace_url("abc123")
        == "https://langfuse.example.com/project/allianz-rag/traces/abc123"
    )


def test_helper_strips_trailing_slash_from_public_url(monkeypatch: object) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_URL", "https://langfuse.example.com/")  # type: ignore[attr-defined]
    monkeypatch.delenv("LANGFUSE_BASE_URL", raising=False)  # type: ignore[attr-defined]
    monkeypatch.setenv("LANGFUSE_PROJECT_ID", "allianz-rag")  # type: ignore[attr-defined]

    assert (
        _langfuse_trace_url("abc123")
        == "https://langfuse.example.com/project/allianz-rag/traces/abc123"
    )


def test_helper_falls_back_to_base_url(monkeypatch: object) -> None:
    monkeypatch.delenv("LANGFUSE_PUBLIC_URL", raising=False)  # type: ignore[attr-defined]
    monkeypatch.setenv("LANGFUSE_BASE_URL", "http://127.0.0.1:3000")  # type: ignore[attr-defined]
    monkeypatch.setenv("LANGFUSE_PROJECT_ID", "allianz-rag")  # type: ignore[attr-defined]

    assert (
        _langfuse_trace_url("abc123") == "http://127.0.0.1:3000/project/allianz-rag/traces/abc123"
    )


def test_helper_returns_none_without_a_project_id(monkeypatch: object) -> None:
    """Without the project the route cannot be built, so emit nothing."""
    monkeypatch.setenv("LANGFUSE_BASE_URL", "http://127.0.0.1:3000")  # type: ignore[attr-defined]
    monkeypatch.delenv("LANGFUSE_PUBLIC_URL", raising=False)  # type: ignore[attr-defined]
    monkeypatch.delenv("LANGFUSE_PROJECT_ID", raising=False)  # type: ignore[attr-defined]

    assert _langfuse_trace_url("abc123") is None


def test_helper_returns_none_when_no_env(monkeypatch: object) -> None:
    monkeypatch.delenv("LANGFUSE_PUBLIC_URL", raising=False)  # type: ignore[attr-defined]
    monkeypatch.delenv("LANGFUSE_BASE_URL", raising=False)  # type: ignore[attr-defined]
    monkeypatch.setenv("LANGFUSE_PROJECT_ID", "allianz-rag")  # type: ignore[attr-defined]

    assert _langfuse_trace_url("abc123") is None


def test_helper_never_emits_the_old_broken_shape(monkeypatch: object) -> None:
    """Regression guard: '/trace/<id>' is not a Langfuse route and 404s."""
    monkeypatch.setenv("LANGFUSE_BASE_URL", "http://127.0.0.1:3000")  # type: ignore[attr-defined]
    monkeypatch.delenv("LANGFUSE_PUBLIC_URL", raising=False)  # type: ignore[attr-defined]
    monkeypatch.setenv("LANGFUSE_PROJECT_ID", "allianz-rag")  # type: ignore[attr-defined]

    url = _langfuse_trace_url("abc123")
    assert url is not None
    assert "/trace/abc123" not in url


def test_helper_returns_none_for_a_blank_trace_id(monkeypatch: object) -> None:
    monkeypatch.setenv("LANGFUSE_BASE_URL", "http://127.0.0.1:3000")  # type: ignore[attr-defined]
    monkeypatch.setenv("LANGFUSE_PROJECT_ID", "allianz-rag")  # type: ignore[attr-defined]

    assert _langfuse_trace_url("   ") is None


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
                rules_evaluated=(
                    RuleEvaluation(
                        rule_id="cide-requires-two-vehicles",
                        inputs=(("vehicle_count", "2"),),
                        result="matched",
                        evidence_ids=("sha256:" + "b" * 64 + ":page:56",),
                        rationale="Dos vehículos con colisión directa.",
                    ),
                ),
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
                    rules_evaluated=(
                        RuleEvaluation(
                            rule_id="cide-requires-two-vehicles",
                            inputs=(("vehicle_count", "2"),),
                            result="matched",
                            evidence_ids=("sha256:" + "b" * 64 + ":page:56",),
                            rationale="Dos vehículos con colisión directa.",
                        ),
                    ),
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
    monkeypatch.setenv("LANGFUSE_PROJECT_ID", "allianz-rag")  # type: ignore[attr-defined]

    env = _build_envelope_question()
    assert env.metadata["trace_id"] == "trace-q"
    assert (
        env.metadata["langfuse_url"]
        == "https://langfuse.example.com/project/allianz-rag/traces/trace-q"
    )


def test_envelope_claim_branch_emits_langfuse_url(monkeypatch: object) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_URL", "https://langfuse.example.com/")  # type: ignore[attr-defined]
    monkeypatch.delenv("LANGFUSE_BASE_URL", raising=False)  # type: ignore[attr-defined]
    monkeypatch.setenv("LANGFUSE_PROJECT_ID", "allianz-rag")  # type: ignore[attr-defined]

    env = _build_envelope_claim()
    assert env.metadata["trace_id"] == "trace-c"
    # Trailing slash on the env value must be normalised away.
    assert (
        env.metadata["langfuse_url"]
        == "https://langfuse.example.com/project/allianz-rag/traces/trace-c"
    )


def test_envelope_clarification_branch_emits_langfuse_url(monkeypatch: object) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_URL", "https://langfuse.example.com")  # type: ignore[attr-defined]
    monkeypatch.delenv("LANGFUSE_BASE_URL", raising=False)  # type: ignore[attr-defined]
    monkeypatch.setenv("LANGFUSE_PROJECT_ID", "allianz-rag")  # type: ignore[attr-defined]

    env = _build_envelope_clarification()
    assert env.metadata["trace_id"] == "trace-cl"
    assert (
        env.metadata["langfuse_url"]
        == "https://langfuse.example.com/project/allianz-rag/traces/trace-cl"
    )
    assert env.metadata["decision"] == "clarification_required"


def test_envelope_auto_question_branch_emits_langfuse_url(monkeypatch: object) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_URL", "https://langfuse.example.com")  # type: ignore[attr-defined]
    monkeypatch.delenv("LANGFUSE_BASE_URL", raising=False)  # type: ignore[attr-defined]
    monkeypatch.setenv("LANGFUSE_PROJECT_ID", "allianz-rag")  # type: ignore[attr-defined]

    env = _build_envelope_auto_question()
    assert env.metadata["trace_id"] == "trace-4"
    assert (
        env.metadata["langfuse_url"]
        == "https://langfuse.example.com/project/allianz-rag/traces/trace-4"
    )


def test_envelope_auto_claim_branch_emits_langfuse_url(monkeypatch: object) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_URL", "https://langfuse.example.com")  # type: ignore[attr-defined]
    monkeypatch.delenv("LANGFUSE_BASE_URL", raising=False)  # type: ignore[attr-defined]
    monkeypatch.setenv("LANGFUSE_PROJECT_ID", "allianz-rag")  # type: ignore[attr-defined]

    env = _build_envelope_auto_claim()
    assert env.metadata["trace_id"] == "trace-5"
    assert (
        env.metadata["langfuse_url"]
        == "https://langfuse.example.com/project/allianz-rag/traces/trace-5"
    )


def test_envelope_emits_no_link_without_a_trace_id(monkeypatch: object) -> None:
    """No trace means no link. A URL ending in '/traces/' would just 404."""

    monkeypatch.setenv("LANGFUSE_PUBLIC_URL", "https://langfuse.example.com")  # type: ignore[attr-defined]
    monkeypatch.delenv("LANGFUSE_BASE_URL", raising=False)  # type: ignore[attr-defined]
    monkeypatch.setenv("LANGFUSE_PROJECT_ID", "allianz-rag")  # type: ignore[attr-defined]

    response = EnvelopeResponse.from_question(
        request_id="req-1",
        execution=QueryExecution(
            result=QuestionAnswer("answered", ()),
            context=(),
            trace_id=None,
        ),
    )

    assert response.metadata["trace_id"] == ""
    assert response.metadata["langfuse_url"] is None
