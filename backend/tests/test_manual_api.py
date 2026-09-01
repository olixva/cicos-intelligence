"""HTTP contracts for registered manual sources and navigable evidence."""

from dataclasses import dataclass, replace
from pathlib import Path
from urllib.parse import quote

from fastapi.testclient import TestClient
from pypdf import PdfWriter

from application.ports.outbound.evidence_repository import EvidenceRepository
from domain.models.document import DocumentManifest
from domain.models.evidence import BinaryAsset, Extraction, PageEvidence
from infrastructure.adapters.outbound.evidence_repository.filesystem_repository import (
    FilesystemEvidenceRepository,
)


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
