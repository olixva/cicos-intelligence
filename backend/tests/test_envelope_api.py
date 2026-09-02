"""HTTP contract for the unified query envelope (Phase 4).

These tests pin:

- The three-mode dispatch table (Oracle Gate 1 must-fix #4):
  ``question`` goes straight to ``AnswerQuestion``, ``claim`` straight
  to ``AnalyzeClaim``, ``auto`` invokes ``ResolveQuery``. The auto
  router is never invoked for explicit modes.
- The closed-enum ``result.kind`` discriminator.
- The synchronous envelope ignores ``stream=true`` and points callers
  to ``/queries/stream`` for that capability.
- The envelope route is mounted only when **all three** ports are
  injected into ``create_app``.
- Validation: blank text 422, ``clarifications`` only in ``mode=claim``
  422, unsupported ``profile`` 422.
- Provider failure surfaces as 500, never as a 200 ``clarification``
  decision.
- No local asset path may leak in any branch of the envelope body.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi.testclient import TestClient

from application.models.claim import ClaimExecution
from application.models.query import (
    AnswerBlock,
    ContextEvidence,
    QueryExecution,
    QueryInput,
    QuestionAnswer,
)
from domain.models.decision import ClaimAnalysis
from domain.models.evidence import PageEvidence
from domain.models.routing import (
    ClarificationResult,
    RouteClassification,
    RouteExecution,
)


@dataclass(frozen=True, slots=True)
class _FakeAnswer:
    last: list[QueryInput] = field(default_factory=list)
    execution: QueryExecution = field(
        default_factory=lambda: QueryExecution(
            result=QuestionAnswer("answered", (AnswerBlock("ok", ("sha256:x:page:1",)),)),
            context=(),
            trace_id="trace-q",
        )
    )

    async def execute(self, query: QueryInput) -> QueryExecution:
        self.last.append(query)
        return self.execution


@dataclass(frozen=True, slots=True)
class _FakeClaim:
    last_text: list[str] = field(default_factory=list)
    execution: ClaimExecution = field(
        default_factory=lambda: ClaimExecution(
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
        )
    )

    async def execute(self, claim) -> ClaimExecution:  # type: ignore[no-untyped-def]
        self.last_text.append(claim.text)
        return self.execution


@dataclass(frozen=True, slots=True)
class _FakeResolve:
    last: list[QueryInput] = field(default_factory=list)
    classification: RouteClassification = field(
        default_factory=lambda: RouteClassification("question")
    )

    async def execute(self, query: QueryInput) -> RouteExecution:
        self.last.append(query)
        if self.classification.decision == "claim":
            dispatch = ClaimExecution(
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
                trace_id="trace-r",
            )
        elif self.classification.decision == "clarification_required":
            dispatch = ClarificationResult(
                message=self.classification.rationale or "necesito datos",
                missing_fields=(),
            )
        else:
            dispatch = QueryExecution(
                result=QuestionAnswer("answered", (AnswerBlock("ok", ("sha256:y:page:2",)),)),
                context=(),
                trace_id="trace-r",
            )
        return RouteExecution(
            query=query,
            classification=self.classification,
            dispatch=dispatch,
            trace_id="trace-r",
        )


def _page() -> PageEvidence:
    return PageEvidence(
        evidence_id="sha256:x:page:1",
        document_hash="abc",
        pdf_page=1,
        text="Texto de la página.",
        printed_label="1",
        image_path="pages/1.png",
        regions=(),
    )


def _client_with_three_ports(
    answer: _FakeAnswer | None = None,
    claim: _FakeClaim | None = None,
    resolve: _FakeResolve | None = None,
    allowed_profiles: tuple[str, ...] = (),
):
    from infrastructure.adapters.inbound.api.app import create_app

    answer = answer or _FakeAnswer()
    claim = claim or _FakeClaim()
    resolve = resolve or _FakeResolve()
    app = create_app(
        answer_question=answer,
        analyze_claim=claim,
        resolve_query=resolve,
        allowed_profiles=allowed_profiles,
    )
    return TestClient(app), answer, claim, resolve


def _post_envelope(client: TestClient, body: dict[str, object]):
    return client.post("/api/v1/queries", json=body)


def test_envelope_dispatches_question_mode_directly_without_invoking_router() -> None:
    """Oracle Gate 1 must-fix: explicit modes bypass the auto router."""

    client, answer, claim, resolve = _client_with_three_ports()

    response = _post_envelope(
        client, {"text": "¿Qué dice el manual?", "language": "es", "mode": "question"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["requested_mode"] == "question"
    assert body["resolved_mode"] == "question"
    assert body["result"]["kind"] == "question"
    assert body["result"]["status"] == "answered"
    assert body["metadata"]["trace_id"] == "trace-q"
    assert len(answer.last) == 1
    assert answer.last[0] == QueryInput("¿Qué dice el manual?", "es")
    assert len(resolve.last) == 0
    assert len(claim.last_text) == 0
    assert "image_path" not in response.text


def test_envelope_dispatches_claim_mode_with_clarifications() -> None:
    client, answer, claim, resolve = _client_with_three_ports()

    response = _post_envelope(
        client,
        {
            "text": "Hubo un choque entre A y B.",
            "language": "es",
            "mode": "claim",
            "clarifications": ["A circulaba en dirección norte"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["requested_mode"] == "claim"
    assert body["resolved_mode"] == "claim"
    assert body["result"]["kind"] == "claim"
    assert body["result"]["applicability"] == "applicable"
    assert body["result"]["convention"] == "CIDE"
    assert body["metadata"]["trace_id"] == "trace-c"
    assert len(claim.last_text) == 1
    assert claim.last_text[0] == "Hubo un choque entre A y B."
    assert len(answer.last) == 0
    assert len(resolve.last) == 0


def test_envelope_dispatches_auto_mode_through_the_router() -> None:
    client, answer, claim, resolve = _client_with_three_ports(
        resolve=_FakeResolve(classification=RouteClassification("claim", rationale="narrative"))
    )

    response = _post_envelope(
        client, {"text": "Siniestro entre A y B.", "language": "es", "mode": "auto"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["requested_mode"] == "auto"
    assert body["resolved_mode"] == "claim"
    assert body["result"]["kind"] == "claim"
    assert len(resolve.last) == 1
    assert resolve.last[0] == QueryInput("Siniestro entre A y B.", "es")
    assert len(answer.last) == 0


def test_envelope_returns_clarification_result_when_router_classifies_as_such() -> None:
    client, *_ = _client_with_three_ports(
        resolve=_FakeResolve(
            classification=RouteClassification("clarification_required", rationale="faltan datos")
        )
    )

    response = _post_envelope(
        client, {"text": "no tengo suficiente contexto", "language": "es", "mode": "auto"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["requested_mode"] == "auto"
    assert body["resolved_mode"] == "clarification"
    assert body["result"]["kind"] == "clarification"
    assert body["result"]["message"] == "faltan datos"


def test_envelope_projects_evidence_items_without_asset_paths() -> None:
    page = _page()
    execution = QueryExecution(
        result=QuestionAnswer("answered", (AnswerBlock("respuesta", (page.evidence_id,)),)),
        context=(
            ContextEvidence(
                evidence_ids=(page.evidence_id,),
                text="texto",
                sources=(page,),
                delivery="text",
            ),
        ),
        trace_id="trace-ev",
    )
    client, *_ = _client_with_three_ports(answer=_FakeAnswer(execution=execution))

    response = _post_envelope(client, {"text": "Pregunta", "language": "es", "mode": "question"})

    assert response.status_code == 200
    body = response.json()
    assert body["evidence"] == [
        {
            "evidence_id": page.evidence_id,
            "document_hash": "abc",
            "pdf_page": 1,
            "delivery": "text",
        }
    ]
    assert "image_path" not in response.text
    assert "/api/v1/manual/pdf" not in response.text


def test_envelope_rejects_blank_text_with_422() -> None:
    client, *_ = _client_with_three_ports()

    response = _post_envelope(client, {"text": "   ", "language": "es", "mode": "question"})

    assert response.status_code == 422


def test_envelope_rejects_clarifications_outside_claim_mode() -> None:
    client, *_ = _client_with_three_ports()

    response = _post_envelope(
        client,
        {
            "text": "Pregunta",
            "language": "es",
            "mode": "question",
            "clarifications": ["no aplica"],
        },
    )

    assert response.status_code == 422


def test_envelope_rejects_unsupported_profile_with_422() -> None:
    client, *_ = _client_with_three_ports(allowed_profiles=("baseline",))

    response = _post_envelope(
        client,
        {
            "text": "Pregunta",
            "language": "es",
            "mode": "question",
            "profile": "phantom",
        },
    )

    assert response.status_code == 422


def test_envelope_accepts_supported_profile() -> None:
    client, *_ = _client_with_three_ports(allowed_profiles=("baseline",))

    response = _post_envelope(
        client,
        {
            "text": "Pregunta",
            "language": "es",
            "mode": "question",
            "profile": "baseline",
        },
    )

    assert response.status_code == 200


def test_envelope_ignores_stream_flag_on_synchronous_route() -> None:
    client, *_ = _client_with_three_ports()

    response = _post_envelope(
        client,
        {"text": "Pregunta", "language": "es", "mode": "question", "stream": True},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")


def test_envelope_keeps_provider_failures_as_500_not_clarification() -> None:
    @dataclass(frozen=True, slots=True)
    class _BoomAnswer:
        async def execute(self, query: QueryInput) -> QueryExecution:
            raise RuntimeError("provider unavailable")

    from infrastructure.adapters.inbound.api.app import create_app

    app = create_app(
        answer_question=_BoomAnswer(),
        analyze_claim=_FakeClaim(),
        resolve_query=_FakeResolve(),
    )
    client = TestClient(app, raise_server_exceptions=False)

    response = _post_envelope(client, {"text": "Pregunta", "language": "es", "mode": "question"})

    assert response.status_code == 500


def test_envelope_is_not_mounted_when_any_port_is_missing() -> None:
    """Per Oracle Q4: envelope requires all three ports."""

    from infrastructure.adapters.inbound.api.app import create_app

    app = create_app(answer_question=_FakeAnswer())
    client = TestClient(app)

    response = client.post(
        "/api/v1/queries", json={"text": "Pregunta", "language": "es", "mode": "question"}
    )

    assert response.status_code == 404


def test_envelope_routes_question_clarifications_in_input() -> None:
    """The query router port never receives ``clarifications`` (only the claim port does)."""

    client, answer, claim, _ = _client_with_three_ports()

    _post_envelope(client, {"text": "Pregunta", "language": "es", "mode": "question"})

    # The query port receives the bare QueryInput (text, language); the
    # claim clarifications tuple is only consumed by the claim port.
    assert len(answer.last) == 1
    assert answer.last[0].text == "Pregunta"
    assert len(claim.last_text) == 0


def test_envelope_request_id_is_server_generated_uuid4() -> None:
    client, *_ = _client_with_three_ports()

    response = _post_envelope(client, {"text": "Pregunta", "language": "es", "mode": "question"})

    body = response.json()
    request_id = body["request_id"]
    # UUID4: 8-4-4-4-12 with version nibble = 4 and variant nibble in {8,9,a,b}
    import re

    pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
    assert re.match(pattern, request_id), f"not a UUID4: {request_id!r}"
