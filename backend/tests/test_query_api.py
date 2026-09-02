"""HTTP contract for the closed-enum auto-router endpoint."""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi.testclient import TestClient

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
    RouteExecution,
)
from domain.models.rule_evaluation import RuleEvaluation


@dataclass(frozen=True, slots=True)
class _FakeResolveQuery:
    last_query: list[QueryInput] = field(default_factory=list)
    execution: RouteExecution | None = None
    raise_exc: Exception | None = None

    async def execute(self, query: QueryInput) -> RouteExecution:
        self.last_query.append(query)
        if self.raise_exc is not None:
            raise self.raise_exc
        assert self.execution is not None
        return self.execution


def _query_execution(trace_id: str) -> RouteExecution:
    return RouteExecution(
        query=QueryInput("Pregunta", "es"),
        classification=type("C", (), {"decision": "question", "rationale": None})(),  # type: ignore[call-arg]
        dispatch=QueryExecution(
            result=QuestionAnswer("answered", (AnswerBlock("ok", ("sha256:x:page:1",)),)),
            context=(),
            trace_id=trace_id,
        ),
        trace_id=trace_id,
    )


def _query_resolve(app, body: dict[str, object]):
    return TestClient(app).post("/api/v1/queries/resolve", json=body)


def test_resolve_route_returns_decision_and_rationale_from_domain() -> None:
    """The route projects the closed-enum decision and the rationale only."""

    from infrastructure.adapters.inbound.api.app import create_app

    execution = RouteExecution(
        query=QueryInput("Pregunta", "es"),
        classification=type("C", (), {"decision": "question", "rationale": "answered"})(),  # type: ignore[call-arg]
        dispatch=QueryExecution(
            result=QuestionAnswer("answered", ()),
            context=(),
            trace_id="trace-abc",
        ),
        trace_id="trace-abc",
    )
    port = _FakeResolveQuery(execution=execution)
    app = create_app(resolve_query=port)

    response = _query_resolve(app, {"text": "Pregunta", "language": "es"})

    assert response.status_code == 200
    assert response.json() == {
        "decision": "question",
        "rationale": "answered",
        "trace_id": "trace-abc",
    }
    assert port.last_query == [QueryInput("Pregunta", "es")]


def test_resolve_route_returns_clarification_decision() -> None:
    from infrastructure.adapters.inbound.api.app import create_app

    execution = RouteExecution(
        query=QueryInput("Faltan datos", "es"),
        classification=type(
            "C",
            (),
            {"decision": "clarification_required", "rationale": "faltan datos"},
        )(),  # type: ignore[call-arg]
        dispatch=ClarificationResult(message="faltan datos", missing_fields=()),
        trace_id="trace-clar",
    )
    app = create_app(resolve_query=_FakeResolveQuery(execution=execution))

    response = _query_resolve(app, {"text": "Faltan datos"})

    assert response.status_code == 200
    assert response.json()["decision"] == "clarification_required"
    assert response.json()["rationale"] == "faltan datos"


def test_resolve_route_never_leaks_local_asset_paths() -> None:
    """Even with a claim-shaped dispatch, no local path may escape."""

    from infrastructure.adapters.inbound.api.app import create_app

    execution = RouteExecution(
        query=QueryInput("Siniestro", "es"),
        classification=type("C", (), {"decision": "claim", "rationale": None})(),  # type: ignore[call-arg]
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
            trace_id="trace-claim",
        ),
        trace_id="trace-claim",
    )
    app = create_app(resolve_query=_FakeResolveQuery(execution=execution))

    response = _query_resolve(app, {"text": "Siniestro"})

    body = response.text
    assert response.status_code == 200
    assert "image_path" not in body
    assert "/api/v1/manual/pdf" not in body
    assert body  # non-empty response body


def test_resolve_route_rejects_blank_text_before_calling_the_use_case() -> None:
    from infrastructure.adapters.inbound.api.app import create_app

    port = _FakeResolveQuery(execution=_query_execution("trace-x"))
    app = create_app(resolve_query=port)

    response = _query_resolve(app, {"text": "   "})

    assert response.status_code == 422
    assert port.last_query == []


def test_resolve_route_rejects_unsupported_language() -> None:
    from infrastructure.adapters.inbound.api.app import create_app

    port = _FakeResolveQuery(execution=_query_execution("trace-x"))
    app = create_app(resolve_query=port)

    response = _query_resolve(app, {"text": "Question", "language": "fr"})

    assert response.status_code == 422
    assert port.last_query == []


def test_resolve_route_keeps_provider_failures_as_technical_errors() -> None:
    """A provider failure surfaces as 500, never as a 'clarification' decision."""

    from infrastructure.adapters.inbound.api.app import create_app

    app = create_app(
        resolve_query=_FakeResolveQuery(raise_exc=RuntimeError("provider unavailable"))
    )
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post("/api/v1/queries/resolve", json={"text": "Pregunta"})

    assert response.status_code == 500


def test_resolve_route_is_not_mounted_when_port_is_absent() -> None:
    """The queries router must not appear if no ``ResolveQuery`` port is injected."""

    from infrastructure.adapters.inbound.api.app import create_app

    app = create_app()
    client = TestClient(app)

    response = client.post("/api/v1/queries/resolve", json={"text": "Pregunta"})

    assert response.status_code == 404
