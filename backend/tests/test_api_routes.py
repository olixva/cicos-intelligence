"""Rutas del API por modo explicito, manual, demo, administracion y composicion."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from application.models.claim import ClaimExecution
from application.models.ingestion import IngestionJobStore
from application.models.query import (
    AnswerBlock,
    ContextEvidence,
    QueryExecution,
    QueryInput,
    QuestionAnswer,
)
from application.ports.outbound.evidence_repository import EvidenceRepository
from domain.models.claim import ClaimEvidenceBlock, ClaimFact, ClaimInput
from domain.models.decision import ClaimAnalysis
from domain.models.document import DocumentManifest
from domain.models.evidence import BinaryAsset, Extraction, PageEvidence
from domain.models.routing import (
    ClarificationResult,
    RouteExecution,
)
from domain.models.rule_evaluation import RuleEvaluation
from infrastructure.adapters.inbound.api.routes.demo import DEFAULT_DEMO_CASE_IDS, build_demo_router
from infrastructure.adapters.outbound.evidence_repository.filesystem_repository import (
    FilesystemEvidenceRepository,
)

# --------------------------------------------------------------------------
# HTTP contract for the explicit document-question route.
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _FakeAnswerQuestion:
    execution: QueryExecution
    received: list[QueryInput]

    async def execute(self, query: QueryInput) -> QueryExecution:
        self.received.append(query)
        return self.execution


def test_question_route_returns_the_grounded_execution_from_the_inbound_port() -> None:
    """Dropping context or trace data would make an answer impossible to audit."""
    from infrastructure.adapters.inbound.api.app import create_app

    page = PageEvidence(
        evidence_id="sha256:abc:page:5",
        document_hash="abc",
        pdf_page=5,
        text="Texto de la página.",
        printed_label="3",
        image_path="pages/5.png",
        regions=(),
    )
    execution = QueryExecution(
        result=QuestionAnswer(
            "answered",
            (AnswerBlock("La respuesta.", (page.evidence_id,)),),
        ),
        context=(
            ContextEvidence(
                evidence_ids=(page.evidence_id,),
                text="Texto de la página.",
                sources=(page,),
                delivery="text",
            ),
        ),
        trace_id="trace-123",
    )
    received: list[QueryInput] = []
    client = TestClient(create_app(answer_question=_FakeAnswerQuestion(execution, received)))

    response = client.post(
        "/api/v1/questions/answer",
        json={"text": "¿Qué dice el manual?", "language": "en"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "answered",
        "blocks": [{"text": "La respuesta.", "evidence_ids": ["sha256:abc:page:5"]}],
        "context": [
            {
                "evidence_ids": ["sha256:abc:page:5"],
                "text": "Texto de la página.",
                "delivery": "text",
                "sources": [
                    {
                        "evidence_id": "sha256:abc:page:5",
                        "document_hash": "abc",
                        "pdf_page": 5,
                        "printed_label": "3",
                    }
                ],
            }
        ],
        "trace_id": "trace-123",
    }
    assert received == [QueryInput("¿Qué dice el manual?", "en")]


def test_question_route_defaults_the_question_language_to_spanish() -> None:
    """Ignoring the transport default would change the model's answer language."""
    from infrastructure.adapters.inbound.api.app import create_app

    received: list[QueryInput] = []
    execution = QueryExecution(QuestionAnswer("insufficient_evidence", ()), ())
    client = TestClient(create_app(answer_question=_FakeAnswerQuestion(execution, received)))

    response = client.post("/api/v1/questions/answer", json={"text": "Pregunta"})

    assert response.status_code == 200
    assert response.json() == {
        "status": "insufficient_evidence",
        "blocks": [],
        "context": [],
        "trace_id": None,
    }
    assert received == [QueryInput("Pregunta", "es")]


def test_question_route_rejects_invalid_input_before_calling_the_use_case() -> None:
    """Passing blank text or an unsupported language to the workflow is an API contract bug."""
    from infrastructure.adapters.inbound.api.app import create_app

    received: list[QueryInput] = []
    execution = QueryExecution(QuestionAnswer("insufficient_evidence", ()), ())
    client = TestClient(create_app(answer_question=_FakeAnswerQuestion(execution, received)))

    blank = client.post("/api/v1/questions/answer", json={"text": "   "})
    unsupported_language = client.post(
        "/api/v1/questions/answer",
        json={"text": "Question", "language": "fr"},
    )

    assert blank.status_code == 422
    assert unsupported_language.status_code == 422
    assert received == []


def test_question_route_keeps_provider_failures_as_technical_errors() -> None:
    """Converting provider failures into insufficient evidence would hide an operational outage."""
    from infrastructure.adapters.inbound.api.app import create_app

    class FailingAnswerQuestion:
        async def execute(self, query: QueryInput) -> QueryExecution:
            raise RuntimeError("provider unavailable")

    client = TestClient(
        create_app(answer_question=FailingAnswerQuestion()),
        raise_server_exceptions=False,
    )

    response = client.post("/api/v1/questions/answer", json={"text": "Pregunta"})

    assert response.status_code == 500


# --------------------------------------------------------------------------
# HTTP contract for the explicit convention-claim analysis route.
# --------------------------------------------------------------------------


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
    bad_language = client.post("/api/v1/claims/analyze", json={"text": "relato", "language": "fr"})

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


# --------------------------------------------------------------------------
# HTTP contract for the closed-enum auto-router endpoint.
# --------------------------------------------------------------------------


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


# --------------------------------------------------------------------------
# HTTP contracts for registered manual sources and navigable evidence.
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PublishedManual:
    root: Path
    parser: str
    manifest: DocumentManifest
    repository: EvidenceRepository
    first: PageEvidence
    last: PageEvidence
    pdf_bytes: bytes


def _publish_manual(tmp_path: Path) -> PublishedManual:
    from infrastructure.adapters.outbound.document_parser.pypdf_parser import PypdfDocumentParser

    source = tmp_path / "manual.pdf"
    writer = PdfWriter()
    for _ in range(111):
        writer.add_blank_page(width=200, height=100)
    writer.write(source)
    pdf_bytes = source.read_bytes()

    extraction = PypdfDocumentParser().parse(source)
    first = replace(
        extraction.pages[0],
        text="Convenios de indemnización directa",
        printed_label="1",
        regions=((20.0, 10.0, 100.0, 50.0),),
        width=200.0,
        height=100.0,
    )
    extraction = replace(
        extraction,
        pages=(first, *extraction.pages[1:]),
        assets=(BinaryAsset("original.pdf", pdf_bytes),),
    )
    root = tmp_path / "extractions"
    repository = FilesystemEvidenceRepository(root, extraction.parser)
    repository.publish(extraction)
    return PublishedManual(
        root=root,
        parser=extraction.parser,
        manifest=extraction.manifest,
        repository=repository,
        first=first,
        last=extraction.pages[-1],
        pdf_bytes=pdf_bytes,
    )


def _client(manual: PublishedManual, *, index_ready: bool = True) -> TestClient:
    from infrastructure.adapters.inbound.api.app import create_app
    from infrastructure.adapters.inbound.api.routes.manual import load_registered_sources

    catalog = load_registered_sources(manual.root, manual.parser)
    app = create_app(
        source_catalog=catalog,
        evidence_repository=manual.repository,
        active_version=manual.manifest.sha256,
        required_index_ready=lambda: index_ready,
    )
    return TestClient(app)


def test_unknown_pdf_version_returns_404_without_falling_back_to_active(
    tmp_path: Path,
) -> None:
    """Replacing a missing version with the active PDF would cite different source bytes."""
    manual = _publish_manual(tmp_path)
    response = _client(manual).get("/api/v1/manual/pdf", params={"version": "0" * 64})

    assert response.status_code == 404
    assert response.json() == {"detail": "Document version not found"}
    assert response.content != manual.pdf_bytes


def test_traversal_inputs_never_open_an_external_file(tmp_path: Path) -> None:
    """Concatenating either HTTP identifier into a filesystem path would expose this marker."""
    manual = _publish_manual(tmp_path)
    marker = b"outside-file-marker"
    (tmp_path / "outside.pdf").write_bytes(marker)
    client = _client(manual)

    pdf_response = client.get("/api/v1/manual/pdf", params={"version": "../../outside.pdf"})
    traversal_id = quote("sha256:../../outside:page:1", safe="")
    evidence_response = client.get(f"/api/v1/manual/evidence/{traversal_id}")

    assert pdf_response.status_code == 404
    assert evidence_response.status_code == 404
    assert marker not in pdf_response.content
    assert marker not in evidence_response.content


def test_registered_manual_pdf_and_metadata_are_bound_to_the_same_hash(
    tmp_path: Path,
) -> None:
    """Returning metadata or bytes from another publication would break source navigation."""
    manual = _publish_manual(tmp_path)
    client = _client(manual)

    metadata = client.get("/api/v1/manual")
    pdf = client.get("/api/v1/manual/pdf", params={"version": manual.manifest.sha256})

    assert metadata.status_code == 200
    assert metadata.json() == {
        "document_id": manual.manifest.document_id,
        "filename": f"{manual.manifest.sha256}.pdf",
        "page_count": 111,
        "pdf_url": f"/api/v1/manual/pdf?version={manual.manifest.sha256}",
        "version": manual.manifest.sha256,
    }
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content == manual.pdf_bytes


def test_evidence_pages_are_resolved_and_regions_are_normalized(tmp_path: Path) -> None:
    """Exposing point coordinates directly would place highlights outside the PDF viewport."""
    manual = _publish_manual(tmp_path)
    client = _client(manual)

    first = client.get(f"/api/v1/manual/evidence/{manual.first.evidence_id}")
    last = client.get(f"/api/v1/manual/evidence/{manual.last.evidence_id}")

    assert first.status_code == 200
    assert first.json() == {
        "document_hash": manual.manifest.sha256,
        "evidence_id": manual.first.evidence_id,
        "pdf_page": 1,
        "pdf_url": f"/api/v1/manual/pdf?version={manual.manifest.sha256}",
        "printed_label": "1",
        "regions": [{"x0": 0.1, "y0": 0.1, "x1": 0.5, "y1": 0.5}],
        "text": "Convenios de indemnización directa",
    }
    assert last.status_code == 200
    assert last.json()["pdf_page"] == 111
    assert last.json()["regions"] == []


def test_missing_evidence_returns_404(tmp_path: Path) -> None:
    """A syntactically valid unknown page must not become an internal repository error."""
    manual = _publish_manual(tmp_path)
    missing_id = f"{manual.manifest.document_id}:page:112"

    response = _client(manual).get(f"/api/v1/manual/evidence/{missing_id}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Evidence not found"}


def test_catalog_rejects_a_publication_whose_registered_pdf_is_corrupt(
    tmp_path: Path,
) -> None:
    """Scanning filenames without publication verification would register altered source bytes."""
    from infrastructure.adapters.inbound.api.routes.manual import load_registered_sources

    manual = _publish_manual(tmp_path)
    publication = manual.root / manual.manifest.sha256 / manual.parser
    (publication / "original.pdf").write_bytes(b"corrupt")

    assert load_registered_sources(manual.root, manual.parser) == {}


def test_health_is_local_and_catalog_alone_does_not_make_the_api_ready(
    tmp_path: Path,
) -> None:
    """Treating a loaded PDF as a built index would admit queries that cannot retrieve."""
    from infrastructure.adapters.inbound.api.app import create_app
    from infrastructure.adapters.inbound.api.routes.manual import load_registered_sources

    manual = _publish_manual(tmp_path)
    checks = 0

    class UnusedRepository:
        def publish(self, extraction: Extraction) -> Path:
            raise AssertionError("health must not publish evidence")

        def get(self, evidence_id: str) -> PageEvidence:
            raise AssertionError("health must not read evidence or call a provider")

        def get_document_pages(self, document_hash: str) -> tuple[PageEvidence, ...]:
            raise AssertionError("health must not read evidence or call a provider")

    def index_is_missing() -> bool:
        nonlocal checks
        checks += 1
        return False

    app = create_app(
        source_catalog=load_registered_sources(manual.root, manual.parser),
        evidence_repository=UnusedRepository(),
        active_version=manual.manifest.sha256,
        required_index_ready=index_is_missing,
    )
    client = TestClient(app)

    live = client.get("/health/live")
    ready = client.get("/health/ready")

    assert live.status_code == 200
    assert live.json() == {"status": "live"}
    assert ready.status_code == 503
    assert ready.json() == {"status": "not_ready"}
    assert checks == 1


def test_resolve_citations_preserves_requested_order(tmp_path: Path) -> None:
    """Sorting citation IDs would detach answer references from their evidence order."""
    from application.services.citations import resolve_citations

    manual = _publish_manual(tmp_path)

    resolved = resolve_citations(
        (manual.last.evidence_id, manual.first.evidence_id), manual.repository
    )

    assert tuple(page.pdf_page for page in resolved) == (111, 1)


# --------------------------------------------------------------------------
# test_demo_api
# --------------------------------------------------------------------------


def test_default_demo_catalogue_covers_the_five_demonstration_outcomes() -> None:
    """La demo ordena dos preguntas y tres siniestros con desenlaces distintos."""
    assert DEFAULT_DEMO_CASE_IDS == (
        "consulta-es-01-alcoholemia",
        "consulta-synth-21-atestado-ascide-cierra",
        "siniestro-synth-12-b9-marcha-atras",
        "accident-02-pile-up-es",
        "accident-04-lane-change-es",
    )


def test_demo_cases_expose_only_safe_development_fields(tmp_path: Path) -> None:
    source = tmp_path / "development.jsonl"
    source.write_text(
        '{"case_id":"c1","text":"relato","language":"es","expected_intent":"claim","expected_output":"oculto"}\n',
        encoding="utf-8",
    )
    app = FastAPI()
    app.include_router(build_demo_router(source, case_ids=("c1",)))
    response = TestClient(app).get("/api/v1/demo/cases")
    assert response.status_code == 200
    assert response.json() == [
        {"case_id": "c1", "text": "relato", "language": "es", "expected_intent": "claim"}
    ]


def test_demo_cases_expose_only_safe_fields_from_full_golden_schema(tmp_path: Path) -> None:
    """The real development.jsonl holds full GoldenDatasetItem records; only input/metadata
    fields the product may show publicly are forwarded, never expected_output or review."""
    source = tmp_path / "development.jsonl"
    source.write_text(
        '{"input":{"text":"relato","language":"es","clarifications":[]},'
        '"expected_output":{"reference":"secreto","decisions":{"intent":"claim"},'
        '"requirements":[{"requirement_id":"r1","description":"oculto"}],'
        '"acceptable_alternatives":[],"forbidden_facts":[],"evidence_requirements":[]},'
        '"metadata":{"case_id":"c1","family_id":"c1","partition":"development",'
        '"review_status":"adjudicated","provenance":{"kind":"interview_example",'
        '"source_ids":["x"]},"language":"es","expected_intent":"claim",'
        '"review":{"reviewer_ids":["r"],"independent_resolution_checked":true,'
        '"evidence_checked":true,"adversarial_checked":true,"adjudication_note":"n",'
        '"open_discrepancies":[]}}}\n',
        encoding="utf-8",
    )
    app = FastAPI()
    app.include_router(build_demo_router(source, case_ids=("c1",)))
    response = TestClient(app).get("/api/v1/demo/cases")
    assert response.status_code == 200
    assert response.json() == [
        {"case_id": "c1", "text": "relato", "language": "es", "expected_intent": "claim"}
    ]
    assert "secreto" not in response.text
    assert "oculto" not in response.text


def test_demo_catalogue_is_curated_and_ordered(tmp_path: Path) -> None:
    """El conjunto de desarrollo crece con la curación; la demo no crece con él.

    Se sirven sólo los casos elegidos y en el orden pedido, y un identificador
    que ya no exista se ignora en lugar de tumbar la interfaz.
    """
    source = tmp_path / "development.jsonl"
    source.write_text(
        "\n".join(
            f'{{"case_id":"{cid}","text":"t","language":"es","expected_intent":"claim"}}'
            for cid in ("uno", "dos", "tres")
        )
        + "\n",
        encoding="utf-8",
    )
    app = FastAPI()
    app.include_router(build_demo_router(source, case_ids=("tres", "no-existe", "uno")))
    response = TestClient(app).get("/api/v1/demo/cases")

    assert response.status_code == 200
    assert [case["case_id"] for case in response.json()] == ["tres", "uno"]


def test_demo_catalogue_uses_a_described_claim_with_one_decisive_missing_fact(
    tmp_path: Path,
) -> None:
    source = tmp_path / "development.jsonl"
    source.write_text(
        '{"case_id":"siniestro-synth-12-b9-marcha-atras","text":"texto original",'
        '"language":"es","expected_intent":"claim"}\n',
        encoding="utf-8",
    )
    app = FastAPI()
    app.include_router(build_demo_router(source, case_ids=("siniestro-synth-12-b9-marcha-atras",)))

    response = TestClient(app).get("/api/v1/demo/cases")

    assert response.status_code == 200
    assert response.json()[0]["text"] == (
        "El vehículo A golpea al vehículo B mientras realiza una maniobra de marcha atrás. "
        "No hay D.A.A. ni atestado."
    )


def test_demo_catalogue_reports_unavailable_when_no_curated_case_exists(tmp_path: Path) -> None:
    source = tmp_path / "development.jsonl"
    source.write_text(
        '{"case_id":"otro","text":"t","language":"es","expected_intent":"claim"}\n',
        encoding="utf-8",
    )
    app = FastAPI()
    app.include_router(build_demo_router(source, case_ids=("no-esta",)))

    assert TestClient(app).get("/api/v1/demo/cases").status_code == 503


# --------------------------------------------------------------------------
# test_admin_ingestion_api
# --------------------------------------------------------------------------


def test_admin_ingestion_starts_one_background_job_and_exposes_snapshot(tmp_path: Path) -> None:
    from application.services.ingestion_jobs import IngestionJobService
    from infrastructure.adapters.inbound.api.app import create_app

    store = IngestionJobStore(tmp_path / "ingestion.json")
    service = IngestionJobService(store)
    started: list[str] = []

    async def runner(job_id: str) -> None:
        started.append(job_id)

    app = create_app(admin_ingestion_service=service, admin_ingestion_runner=runner)
    with TestClient(app) as client:
        assert client.get("/api/v1/admin/ingestion").json()["active_job"] is None
        response = client.post("/api/v1/admin/ingestion")
        assert response.status_code == 202
        job_id = response.json()["job_id"]
        assert response.json()["status"] == "running"
        assert client.get("/api/v1/admin/ingestion").json()["active_job"]["job_id"] == job_id
        assert client.post("/api/v1/admin/ingestion").status_code == 409
    assert started == [job_id]


def test_admin_ingestion_events_emit_persisted_terminal_event(tmp_path: Path) -> None:
    from datetime import UTC, datetime

    from application.models.ingestion import IngestionEvent
    from application.services.ingestion_jobs import IngestionJobService
    from infrastructure.adapters.inbound.api.app import create_app

    store = IngestionJobStore(tmp_path / "ingestion.json")
    service = IngestionJobService(store)
    job = service.start()
    store.append_event(
        job.job_id,
        IngestionEvent(
            event_id="evt-terminal",
            job_id=job.job_id,
            timestamp=datetime.now(UTC),
            stage="published_index",
            status="succeeded",
            data={"chunks": 118},
        ),
    )
    store.update(job.job_id, status="succeeded", stage="published_index")
    app = create_app(admin_ingestion_service=service)

    with TestClient(app) as client:
        response = client.get("/api/v1/admin/ingestion/events")
    assert response.status_code == 200
    assert "evt-terminal" in response.text
    assert '"status": "succeeded"' in response.text


def test_admin_ingestion_extractions_returns_only_public_page_summary(tmp_path: Path) -> None:
    from domain.models.evidence import PageEvidence
    from infrastructure.adapters.inbound.api.app import create_app

    class Repository:
        def get_document_pages(self, document_hash: str) -> tuple[PageEvidence, ...]:
            return (
                PageEvidence(
                    evidence_id=f"sha256:{document_hash}:page:1",
                    document_hash=document_hash,
                    pdf_page=1,
                    text="Texto extraído del manual.",
                    printed_label="1",
                    image_path="private/path.png",
                    regions=((1.0, 2.0, 3.0, 4.0),),
                ),
            )

    app = create_app(
        admin_ingestion_service=None,
        admin_ingestion_repository=Repository(),
        admin_ingestion_document_hash="a" * 64,
    )
    with TestClient(app) as client:
        response = client.get("/api/v1/admin/ingestion/extractions?offset=0&limit=1")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["pdf_page"] == 1
    assert body["items"][0]["regions_available"] is True
    assert "image_path" not in response.text


# --------------------------------------------------------------------------
# Bootstrap-level wiring for ``build_api`` partial-failure behavior.
#
# These tests pin the contract that ``build_api`` keeps mounting the surviving
# port when one factory raises, surfaces the skip through the module logger
# rather than ``sys.stderr``, and aggregates total failure into a hard
# ``RuntimeError``.
# --------------------------------------------------------------------------


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

    with pytest.raises(RuntimeError, match=r"build_api\(\) could not compose any workflow port"):
        bootstrap.build_api(question_profile="q", claim_profile="c")
