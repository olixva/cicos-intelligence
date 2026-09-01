"""HTTP contract for the explicit convention-claim analysis route."""

from dataclasses import dataclass, field

from fastapi.testclient import TestClient

from application.models.claim import ClaimExecution
from application.models.query import ContextEvidence
from domain.models.claim import ClaimEvidenceBlock, ClaimFact, ClaimInput
from domain.models.decision import ClaimAnalysis
from domain.models.evidence import PageEvidence


@dataclass
class _FakeAnalyzeClaim:
    """Spy/port double; records every call and returns the configured execution."""

    execution: ClaimExecution
    received: list[ClaimInput] = field(default_factory=list)

    async def execute(self, claim: ClaimInput) -> ClaimExecution:
        self.received.append(claim)
        return self.execution


def _build_page(
    *,
    evidence_id: str = "sha256:abc:page:5",
    document_hash: str = "abc",
    pdf_page: int = 5,
    image_path: str | None = "pages/5.png",
    regions: tuple[tuple[float, float, float, float], ...] = (),
    width: float | None = None,
    height: float | None = None,
) -> PageEvidence:
    return PageEvidence(
        evidence_id=evidence_id,
        document_hash=document_hash,
        pdf_page=pdf_page,
        text="Texto de la página.",
        printed_label="5",
        image_path=image_path,
        regions=regions,
        width=width,
        height=height,
    )


def _build_execution(
    *,
    page: PageEvidence,
    fact: ClaimFact,
    decision: ClaimAnalysis,
) -> ClaimExecution:
    """Build a ClaimExecution that exercises every DTO branch."""

    return ClaimExecution(
        result=decision,
        context=(
            ContextEvidence(
                evidence_ids=(page.evidence_id,),
                text="Fragmento entregado.",
                sources=(page,),
                delivery="text",
            ),
        ),
        trace_id="trace-123",
    )


def _full_analysis(*, page: PageEvidence, fact: ClaimFact) -> ClaimAnalysis:
    return ClaimAnalysis(
        applicability="applicable",
        convention="CIDE",
        decision="conditional",
        party_ids=("A", "B"),
        facts=(fact,),
        contradictions=(),
        conditions=("A y B confirman vehículos distintos.",),
        missing_information=("Velocidad relativa.",),
        blocks=(
            ClaimEvidenceBlock(
                text="El convenio aplica cuando hay dos vehículos y colisión directa.",
                evidence_ids=(page.evidence_id,),
            ),
        ),
    )


def test_claim_router_is_only_mounted_when_analyze_claim_is_injected() -> None:
    """Mounting the route by default would expose a workflow that has no real backing."""

    from infrastructure.adapters.inbound.api.app import create_app

    execution = ClaimExecution(
        result=ClaimAnalysis(
            applicability="undetermined",
            convention=None,
            decision="not_assessed",
            party_ids=("A",),
            facts=(),
            contradictions=(),
            conditions=(),
            missing_information=(),
            blocks=(),
        ),
        context=(),
    )

    without_port = TestClient(create_app())
    with_port = TestClient(create_app(analyze_claim=_FakeAnalyzeClaim(execution=execution)))

    assert without_port.post("/api/v1/claims/analyze", json={"text": "x"}).status_code == 404
    assert with_port.post("/api/v1/claims/analyze", json={"text": "y"}).status_code == 200


def test_claim_route_returns_full_response_shape_from_inbound_port() -> None:
    """Trimming any field would drop the audit-relevant output of the workflow."""

    from infrastructure.adapters.inbound.api.app import create_app

    page = _build_page(
        evidence_id="sha256:abc:page:5",
        regions=((20.0, 10.0, 100.0, 50.0),),
        width=200.0,
        height=100.0,
    )
    fact = ClaimFact(
        name="vehicles",
        value="dos",
        asserted_by="user",
        source_text="relato: dos vehículos colisionaron",
    )
    analysis = _full_analysis(page=page, fact=fact)
    received: list[ClaimInput] = []
    fake = _FakeAnalyzeClaim(
        execution=_build_execution(page=page, fact=fact, decision=analysis),
        received=received,
    )
    client = TestClient(create_app(analyze_claim=fake))

    response = client.post(
        "/api/v1/claims/analyze",
        json={
            "text": "Tuve un choque entre mi coche y otro.",
            "language": "es",
            "clarifications": ["Ninguno iba a más de 50 km/h."],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "applicability": "applicable",
        "convention": "CIDE",
        "decision": "conditional",
        "parties": ["A", "B"],
        "attributed_facts": [
            {
                "name": "vehicles",
                "value": "dos",
                "asserted_by": "user",
                "source_text": "relato: dos vehículos colisionaron",
            }
        ],
        "contradictions": [],
        "conditions": ["A y B confirman vehículos distintos."],
        "missing_information": ["Velocidad relativa."],
        "evidence_blocks": [
            {
                "text": "El convenio aplica cuando hay dos vehículos y colisión directa.",
                "evidence_ids": ["sha256:abc:page:5"],
            }
        ],
        "delivered_context": [
            {
                "context_id": "sha256:abc:page:5",
                "document_id": "abc",
                "version": "abc",
                "page": 5,
                "region": {"x0": 0.1, "y0": 0.1, "x1": 0.5, "y1": 0.5},
            }
        ],
        "trace_id": "trace-123",
    }
    assert received == [
        ClaimInput(
            text="Tuve un choque entre mi coche y otro.",
            language="es",
            clarifications=("Ninguno iba a más de 50 km/h.",),
        )
    ]


def test_claim_route_never_returns_image_path_or_local_asset_paths() -> None:
    """An image_path on the domain source must not leak into the JSON response."""

    from infrastructure.adapters.inbound.api.app import create_app

    page = _build_page(image_path="secret/payments/5.png")
    fact = ClaimFact(name="vehicles", value="dos", asserted_by="user", source_text="dos coches")
    analysis = ClaimAnalysis(
        applicability="applicable",
        convention="CIDE",
        decision="conditional",
        party_ids=("A", "B"),
        facts=(fact,),
        contradictions=(),
        conditions=("Confirmar vehículos.",),
        missing_information=(),
        blocks=(ClaimEvidenceBlock(text="Bloque.", evidence_ids=(page.evidence_id,)),),
    )
    client = TestClient(
        create_app(
            analyze_claim=_FakeAnalyzeClaim(
                execution=_build_execution(page=page, fact=fact, decision=analysis)
            )
        )
    )

    response = client.post("/api/v1/claims/analyze", json={"text": "Colisión entre dos coches."})

    assert response.status_code == 200
    body = response.text
    forbidden_markers = (
        "image_path",
        "secret/payments/5.png",
        "original.pdf",
        "/Users/",
        "data/extractions",
    )
    for marker in forbidden_markers:
        assert marker not in body, f"forbidden marker {marker!r} must not appear in the response"


def test_claim_route_rejects_invalid_request_payloads_with_422() -> None:
    """Empty, missing, or unsupported-language inputs must fail validation before the port."""

    from infrastructure.adapters.inbound.api.app import create_app

    received: list[ClaimInput] = []
    client = TestClient(
        create_app(
            analyze_claim=_FakeAnalyzeClaim(
                execution=ClaimExecution(
                    result=ClaimAnalysis(
                        applicability="undetermined",
                        convention=None,
                        decision="not_assessed",
                        party_ids=("A",),
                        facts=(),
                        contradictions=(),
                        conditions=(),
                        missing_information=(),
                        blocks=(),
                    ),
                    context=(),
                ),
                received=received,
            )
        )
    )

    empty_text = client.post("/api/v1/claims/analyze", json={"text": "   "})
    missing_text = client.post("/api/v1/claims/analyze", json={})
    bad_language = client.post(
        "/api/v1/claims/analyze", json={"text": "relato", "language": "fr"}
    )

    assert empty_text.status_code == 422
    assert missing_text.status_code == 422
    assert bad_language.status_code == 422
    assert received == []


def test_claim_route_delegates_to_the_inbound_port_with_the_dto() -> None:
    """The DTO the port receives must mirror the HTTP request shape."""

    from infrastructure.adapters.inbound.api.app import create_app

    received: list[ClaimInput] = []
    execution = ClaimExecution(
        result=ClaimAnalysis(
            applicability="undetermined",
            convention=None,
            decision="not_assessed",
            party_ids=("A",),
            facts=(),
            contradictions=(),
            conditions=(),
            missing_information=(),
            blocks=(),
        ),
        context=(),
    )
    client = TestClient(
        create_app(analyze_claim=_FakeAnalyzeClaim(execution=execution, received=received))
    )

    response = client.post(
        "/api/v1/claims/analyze",
        json={"text": "Hubo tres coches.", "language": "en"},
    )

    assert response.status_code == 200
    assert received == [ClaimInput(text="Hubo tres coches.", language="en", clarifications=())]


def test_claim_route_keeps_provider_failures_as_technical_errors() -> None:
    """A provider failure must surface as a 500; it must not become a domain abstention."""

    from infrastructure.adapters.inbound.api.app import create_app

    class FailingAnalyzeClaim:
        async def execute(self, claim: ClaimInput) -> ClaimExecution:
            raise RuntimeError("provider unavailable")

    client = TestClient(
        create_app(analyze_claim=FailingAnalyzeClaim()),
        raise_server_exceptions=False,
    )

    response = client.post("/api/v1/claims/analyze", json={"text": "Choque entre dos coches."})

    assert response.status_code == 500
