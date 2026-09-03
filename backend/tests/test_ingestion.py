"""Ingesta: inspeccion, contrato de publicacion, evidencia estructurada y ejecucion."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest
from pypdf import PdfWriter

from application.models.ingestion import (
    IngestionAlreadyRunning,
    IngestionEvent,
    IngestionJobStore,
    IngestionSnapshot,
)
from application.services.ingestion_runner import IngestionRunner
from application.use_cases.build_retrieval_index_use_case import IndexBuildResult
from domain.models.document import DocumentManifest
from domain.models.evidence import BinaryAsset, Extraction, PageEvidence
from infrastructure.adapters.outbound.document_parser.pypdf_parser import PypdfDocumentParser
from infrastructure.adapters.outbound.evidence_repository.filesystem_repository import (
    EvidenceNotFoundError,
    EvidencePublicationError,
    FilesystemEvidenceRepository,
)

# --------------------------------------------------------------------------
# test_inspect_manual
# --------------------------------------------------------------------------


def test_rejects_an_unexpected_document(tmp_path: Path) -> None:
    """Changing the expected digest must prevent a manifest from being returned."""
    from bootstrap import build_inspect_manual
    from domain.models.document import SourceIntegrityError

    source = tmp_path / "manual.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(str(source))

    with pytest.raises(SourceIntegrityError):
        build_inspect_manual().execute(source, expected_sha256="0" * 64)


def test_returns_manifest_with_hash_filename_and_page_count(tmp_path: Path) -> None:
    """Changing any input byte or page must change the exposed manifest facts."""
    from bootstrap import build_inspect_manual

    source = tmp_path / "manual.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_blank_page(width=300, height=300)
    writer.write(str(source))
    expected_hash = sha256(source.read_bytes()).hexdigest()

    manifest = build_inspect_manual().execute(source, expected_sha256=expected_hash)

    assert manifest.document_id == f"sha256:{expected_hash}"
    assert manifest.sha256 == expected_hash
    assert manifest.filename == "manual.pdf"
    assert manifest.page_count == 2


def test_rejects_non_pdf_bytes(tmp_path: Path) -> None:
    """Replacing a PDF with arbitrary bytes must reject the source as unreadable."""
    from bootstrap import build_inspect_manual
    from domain.models.document import SourceInspectionError

    source = tmp_path / "not-a-pdf.pdf"
    source.write_bytes(b"not a PDF")

    with pytest.raises(SourceInspectionError, match="readable PDF"):
        build_inspect_manual().execute(source)


def test_rejects_a_missing_source(tmp_path: Path) -> None:
    """Removing the source file must produce a readable input error."""
    from bootstrap import build_inspect_manual
    from domain.models.document import SourceInspectionError

    with pytest.raises(SourceInspectionError, match="Unable to read source"):
        build_inspect_manual().execute(tmp_path / "missing.pdf")


def test_rejects_an_encrypted_pdf(tmp_path: Path) -> None:
    """Encrypting an otherwise valid PDF must prevent inspection."""
    from bootstrap import build_inspect_manual
    from domain.models.document import SourceInspectionError

    source = tmp_path / "encrypted.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.encrypt("secret")
    writer.write(str(source))

    with pytest.raises(SourceInspectionError, match="Encrypted PDF"):
        build_inspect_manual().execute(source)


def test_rejects_a_pdf_without_pages(tmp_path: Path) -> None:
    """Removing all pages from a structurally valid PDF must reject the source."""
    from bootstrap import build_inspect_manual
    from domain.models.document import SourceInspectionError

    source = tmp_path / "empty.pdf"
    PdfWriter().write(str(source))

    with pytest.raises(SourceInspectionError, match="at least one page"):
        build_inspect_manual().execute(source)


# --------------------------------------------------------------------------
# test_baseline_ingestion
# --------------------------------------------------------------------------


def _blank_pdf(path: Path, pages: int = 2) -> None:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    writer.write(str(path))


def test_keeps_empty_pages(tmp_path: Path) -> None:
    """Dropping a physical blank page would lose evidence from the manual."""
    from infrastructure.adapters.outbound.document_parser.pypdf_parser import PypdfDocumentParser

    source = tmp_path / "blank.pdf"
    _blank_pdf(source)

    extraction = PypdfDocumentParser().parse(source)

    assert [page.pdf_page for page in extraction.pages] == [1, 2]
    assert [page.text for page in extraction.pages] == ["", ""]
    assert extraction.warnings == (
        "Page 1 did not yield extractable text",
        "Page 2 did not yield extractable text",
    )


def test_publishes_complete_page_evidence_under_its_parser_version(tmp_path: Path) -> None:
    """Changing a page or parser must not overwrite the recorded page evidence."""
    from infrastructure.adapters.outbound.document_parser.pypdf_parser import PypdfDocumentParser
    from infrastructure.adapters.outbound.evidence_repository.filesystem_repository import (
        EvidencePublicationError,
        FilesystemEvidenceRepository,
    )

    source = tmp_path / "blank.pdf"
    _blank_pdf(source)
    extraction = PypdfDocumentParser().parse(source)
    repository = FilesystemEvidenceRepository(tmp_path / "extractions", extraction.parser)

    published = repository.publish(extraction)

    assert published == tmp_path / "extractions" / extraction.manifest.sha256 / extraction.parser
    assert json.loads((published / "manifest.json").read_text()) == {
        "document_id": extraction.manifest.document_id,
        "filename": f"{extraction.manifest.sha256}.pdf",
        "page_count": 2,
        "sha256": extraction.manifest.sha256,
    }
    page_lines = (published / "pages.jsonl").read_text().splitlines()
    assert [json.loads(line)["pdf_page"] for line in page_lines] == [1, 2]
    assert repository.get(extraction.pages[1].evidence_id) == extraction.pages[1]

    altered_page = replace(extraction.pages[0], text="changed evidence")
    altered = replace(extraction, pages=(altered_page, extraction.pages[1]))
    with pytest.raises(EvidencePublicationError, match="different content"):
        repository.publish(altered)
    assert repository.get(extraction.pages[0].evidence_id).text == ""


def test_aborted_publication_leaves_no_final_evidence_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A write error must not expose a partially-written evidence version."""
    from infrastructure.adapters.outbound.document_parser.pypdf_parser import PypdfDocumentParser
    from infrastructure.adapters.outbound.evidence_repository import filesystem_repository
    from infrastructure.adapters.outbound.evidence_repository.filesystem_repository import (
        FilesystemEvidenceRepository,
    )

    source = tmp_path / "blank.pdf"
    _blank_pdf(source)
    extraction = PypdfDocumentParser().parse(source)
    repository = FilesystemEvidenceRepository(tmp_path / "extractions", extraction.parser)
    original_dump = filesystem_repository.json.dump
    calls = 0

    def fail_during_second_page(obj: object, file: Any, **kwargs: Any) -> None:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise OSError("disk full")
        original_dump(obj, file, **kwargs)

    monkeypatch.setattr(filesystem_repository.json, "dump", fail_during_second_page)

    with pytest.raises(OSError, match="disk full"):
        repository.publish(extraction)

    assert not (tmp_path / "extractions" / extraction.manifest.sha256 / extraction.parser).exists()


def test_get_rejects_identifier_that_cannot_name_a_page(tmp_path: Path) -> None:
    """A supplied identifier must never be usable as a filesystem path."""
    from infrastructure.adapters.outbound.evidence_repository.filesystem_repository import (
        EvidenceNotFoundError,
        FilesystemEvidenceRepository,
    )

    repository = FilesystemEvidenceRepository(tmp_path / "extractions", "pypdf-6.16.2")

    with pytest.raises(EvidenceNotFoundError, match="Invalid evidence identifier"):
        repository.get("sha256:../../outside:page:1")


def test_get_rejects_a_malformed_stored_page_record(tmp_path: Path) -> None:
    """Corrupt JSON must remain a repository error rather than leak an implementation error."""
    from infrastructure.adapters.outbound.document_parser.pypdf_parser import PypdfDocumentParser
    from infrastructure.adapters.outbound.evidence_repository.filesystem_repository import (
        EvidenceNotFoundError,
        FilesystemEvidenceRepository,
    )

    source = tmp_path / "blank.pdf"
    _blank_pdf(source)
    extraction = PypdfDocumentParser().parse(source)
    repository = FilesystemEvidenceRepository(tmp_path / "extractions", extraction.parser)
    published = repository.publish(extraction)
    (published / "pages.jsonl").write_text("[]\n", encoding="utf-8")

    with pytest.raises(EvidenceNotFoundError, match="Stored evidence is inconsistent"):
        repository.get(extraction.pages[0].evidence_id)


def test_get_rejects_a_corrupt_stored_manifest(tmp_path: Path) -> None:
    """A page cannot be trusted when its persisted manifest is malformed."""
    from infrastructure.adapters.outbound.document_parser.pypdf_parser import PypdfDocumentParser
    from infrastructure.adapters.outbound.evidence_repository.filesystem_repository import (
        EvidenceNotFoundError,
        FilesystemEvidenceRepository,
    )

    source = tmp_path / "blank.pdf"
    _blank_pdf(source)
    extraction = PypdfDocumentParser().parse(source)
    repository = FilesystemEvidenceRepository(tmp_path / "extractions", extraction.parser)
    published = repository.publish(extraction)
    (published / "manifest.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(EvidenceNotFoundError, match="Stored evidence is inconsistent"):
        repository.get(extraction.pages[0].evidence_id)


def test_get_rejects_page_with_a_mismatched_document_hash(tmp_path: Path) -> None:
    """A returned page must be tied to the hash encoded in its evidence identifier."""
    from infrastructure.adapters.outbound.document_parser.pypdf_parser import PypdfDocumentParser
    from infrastructure.adapters.outbound.evidence_repository.filesystem_repository import (
        EvidenceNotFoundError,
        FilesystemEvidenceRepository,
    )

    source = tmp_path / "blank.pdf"
    _blank_pdf(source)
    extraction = PypdfDocumentParser().parse(source)
    repository = FilesystemEvidenceRepository(tmp_path / "extractions", extraction.parser)
    published = repository.publish(extraction)
    records = [json.loads(line) for line in (published / "pages.jsonl").read_text().splitlines()]
    records[0]["document_hash"] = "0" * 64
    (published / "pages.jsonl").write_text(
        "".join(f"{json.dumps(record, sort_keys=True)}\n" for record in records), encoding="utf-8"
    )

    with pytest.raises(EvidenceNotFoundError, match="Stored evidence is inconsistent"):
        repository.get(extraction.pages[0].evidence_id)


def test_get_rejects_page_with_non_string_text(tmp_path: Path) -> None:
    """Text evidence must retain its stored type instead of coercing corruption to text."""
    from infrastructure.adapters.outbound.document_parser.pypdf_parser import PypdfDocumentParser
    from infrastructure.adapters.outbound.evidence_repository.filesystem_repository import (
        EvidenceNotFoundError,
        FilesystemEvidenceRepository,
    )

    source = tmp_path / "blank.pdf"
    _blank_pdf(source)
    extraction = PypdfDocumentParser().parse(source)
    repository = FilesystemEvidenceRepository(tmp_path / "extractions", extraction.parser)
    published = repository.publish(extraction)
    records = [json.loads(line) for line in (published / "pages.jsonl").read_text().splitlines()]
    records[0]["text"] = 42
    (published / "pages.jsonl").write_text(
        "".join(f"{json.dumps(record, sort_keys=True)}\n" for record in records), encoding="utf-8"
    )

    with pytest.raises(EvidenceNotFoundError, match="Stored evidence is inconsistent"):
        repository.get(extraction.pages[0].evidence_id)


# --------------------------------------------------------------------------
# Contract tests for the immutable ingestion publication.
#
# These tests formalize the unified publication contract so that both
# pypdf and Docling produce interchangeable directories, and so that
# reconstructing a publication from the original PDF is reproducible.
#
# See plan T2: "Publicaciones de ingestión inmutables y comparables".
# --------------------------------------------------------------------------


EXPECTED_SHA256 = "b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344"


@dataclass(frozen=True)
class _Source:
    path: Path
    digest: str


@pytest.fixture
def synthetic_source(tmp_path: Path) -> _Source:
    source = tmp_path / "manual.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_blank_page(width=200, height=200)
    writer.write(source)
    data = source.read_bytes()
    import hashlib

    return _Source(path=source, digest=hashlib.sha256(data).hexdigest())


def _required_paths(directory: Path) -> set[str]:
    return {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()}


def _build_publication(extraction: Extraction, root: Path) -> Path:
    repo = FilesystemEvidenceRepository(root=root, parser=extraction.parser)
    return repo.publish(extraction)


def test_pypdf_publication_includes_original_pdf(synthetic_source: _Source, tmp_path: Path) -> None:
    """The pypdf baseline must publish the source PDF like Docling does."""
    parser = PypdfDocumentParser()
    extraction = parser.parse(synthetic_source.path)

    assert extraction.assets, "Pypdf parser must declare at least the source PDF asset"
    paths = {asset.path for asset in extraction.assets}
    assert "original.pdf" in paths

    repository_root = tmp_path / "extractions"
    published = _build_publication(extraction, repository_root)
    files = _required_paths(published)
    assert "original.pdf" in files, "Published directory must contain original.pdf"
    assert "manifest.json" in files
    assert "pages.jsonl" in files
    assert "publication.json" in files


def test_manifest_records_source_identity(synthetic_source: _Source, tmp_path: Path) -> None:
    """The manifest must capture document id, sha256 and page count."""
    parser = PypdfDocumentParser()
    extraction = parser.parse(synthetic_source.path)

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "document_id": extraction.manifest.document_id,
                "sha256": extraction.manifest.sha256,
                "filename": f"{extraction.manifest.sha256}.pdf",
                "page_count": extraction.manifest.page_count,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    record = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert record["sha256"] == synthetic_source.digest
    assert record["document_id"] == f"sha256:{synthetic_source.digest}"
    assert record["page_count"] == 2


def test_publication_root_binds_every_asset(synthetic_source: _Source, tmp_path: Path) -> None:
    """publication.json must enumerate and hash every byte in the publication."""
    parser = PypdfDocumentParser()
    extraction = parser.parse(synthetic_source.path)

    published = _build_publication(extraction, tmp_path / "extractions")
    publication = json.loads((published / "publication.json").read_text(encoding="utf-8"))

    assert publication["schema_version"] == 1
    paths = {entry["path"] for entry in publication["files"]}
    assert {"manifest.json", "pages.jsonl", "original.pdf"} <= paths
    for entry in publication["files"]:
        target = published / entry["path"]
        assert target.read_bytes().__len__() == entry["size"]
        assert re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]) is not None
    # root_sha256 must match the canonical encoding
    canonical_payload = {"schema_version": 1, "files": publication["files"]}
    canonical = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":")) + "\n"
    import hashlib

    assert publication["root_sha256"] == hashlib.sha256(canonical.encode()).hexdigest()


def test_pypdf_publication_is_idempotent(synthetic_source: _Source, tmp_path: Path) -> None:
    """Re-publishing the same extraction must not duplicate or diverge."""
    parser = PypdfDocumentParser()
    extraction = parser.parse(synthetic_source.path)
    root = tmp_path / "extractions"

    first = _build_publication(extraction, root)
    second = _build_publication(extraction, root)
    assert first == second
    assert _required_paths(first) == _required_paths(second)


def test_pypdf_keeps_blank_pages(synthetic_source: _Source) -> None:
    """Blank pages must be preserved with their physical index."""
    parser = PypdfDocumentParser()
    extraction = parser.parse(synthetic_source.path)

    assert [page.pdf_page for page in extraction.pages] == [1, 2]
    assert all(page.text == "" for page in extraction.pages)
    assert any("did not yield extractable text" in warning for warning in extraction.warnings)


def test_parser_identity_is_explicit(synthetic_source: _Source) -> None:
    """The parser identity must be a deterministic, non-empty string."""
    parser = PypdfDocumentParser()
    extraction = parser.parse(synthetic_source.path)
    assert extraction.parser.startswith("pypdf-")
    assert extraction.parser != "pypdf"
    assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", extraction.parser)


def _two_page_extraction(manifest_hash: str, text_a: str, text_b: str) -> Extraction:
    return Extraction(
        manifest=__manifest(manifest_hash, 2),
        pages=(
            PageEvidence(
                evidence_id=f"sha256:{manifest_hash}:page:1",
                document_hash=manifest_hash,
                pdf_page=1,
                text=text_a,
                printed_label=None,
                image_path=None,
                regions=(),
            ),
            PageEvidence(
                evidence_id=f"sha256:{manifest_hash}:page:2",
                document_hash=manifest_hash,
                pdf_page=2,
                text=text_b,
                printed_label=None,
                image_path=None,
                regions=(),
            ),
        ),
        parser="contract-test-parser",
        warnings=(),
        assets=(BinaryAsset("original.pdf", b"%PDF-1.4\n%fake bytes"),),
    )


def __manifest(digest: str, pages: int):  # type: ignore[no-untyped-def]
    from domain.models.document import DocumentManifest

    return DocumentManifest(
        document_id=f"sha256:{digest}", sha256=digest, filename=f"{digest}.pdf", page_count=pages
    )


@pytest.fixture
def comparison_workspace(tmp_path: Path) -> Iterator[Path]:
    yield tmp_path


def test_comparison_reports_text_coverage(comparison_workspace: Path) -> None:
    """The T2 comparison helper must report textual coverage per parser."""
    from compare_parsers import compare_extractions  # type: ignore[import-not-found]

    digest = "a" * 64
    a = _two_page_extraction(digest, "primera página", "segunda página")
    b = _two_page_extraction(digest, "primera página algo más", "segunda página")

    report = compare_extractions(a, b)
    assert report["page_count"] == 2
    assert "textual_coverage_left_in_right" in report
    assert "textual_coverage_right_in_left" in report
    assert report["textual_coverage_left_in_right"] == pytest.approx(1.0, abs=1e-6)
    assert 0.0 < report["textual_coverage_right_in_left"] < 1.0


# --------------------------------------------------------------------------
# Publication checks use real bytes so incomplete or corrupt evidence is observable.
# --------------------------------------------------------------------------


def _source(path: Path) -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=100)
    writer.write(path)
    return path.read_bytes()


def test_assets_are_immutable_complete_and_round_trip(tmp_path: Path) -> None:
    """Dropping assets, elements, or warnings from publication must break this test."""
    from domain.models.evidence import BinaryAsset, ElementEvidence

    source = tmp_path / "source.pdf"
    original = _source(source)
    base = PypdfDocumentParser().parse(source)
    element = ElementEvidence(
        element_id=f"{base.manifest.document_id}:element:texts:0",
        kind="footnote",
        text="Keep this note",
        section="Coverage",
        content_layer="furniture",
        regions=((10.0, 20.0, 100.0, 40.0),),
    )
    page = replace(base.pages[0], image_path="pages/1.png", elements=(element,))
    extraction = replace(
        base,
        pages=(page,),
        assets=(
            BinaryAsset("original.pdf", original),
            BinaryAsset("pages/1.png", b"png-bytes"),
        ),
    )
    repository = FilesystemEvidenceRepository(tmp_path / "output", extraction.parser)
    published = repository.publish(extraction)
    assert (published / "original.pdf").read_bytes() == original
    assert (published / "pages/1.png").read_bytes() == b"png-bytes"
    assert repository.get(page.evidence_id) == page
    assert json.loads((published / "extraction.json").read_text())["warnings"] == list(
        base.warnings
    )
    assert repository.publish(extraction) == published
    (published / "pages/1.png").write_bytes(b"corrupted")
    with pytest.raises(EvidencePublicationError, match="different content"):
        repository.publish(extraction)


def test_get_document_pages_returns_only_a_complete_verified_publication(tmp_path: Path) -> None:
    """Indexing must consume the same complete, immutable evidence as the citation API."""
    source = tmp_path / "source.pdf"
    _source(source)
    extraction = PypdfDocumentParser().parse(source)
    repository = FilesystemEvidenceRepository(tmp_path / "output", extraction.parser)
    published = repository.publish(extraction)

    assert repository.get_document_pages(extraction.manifest.sha256) == extraction.pages

    (published / "pages.jsonl").write_text("{}\n", encoding="utf-8")
    with pytest.raises(EvidenceNotFoundError, match="inconsistent"):
        repository.get_document_pages(extraction.manifest.sha256)


@pytest.mark.parametrize(
    "paths",
    [
        ("../escaped",),
        ("/absolute",),
        ("pages/../escaped",),
        ("pages//one",),
        ("pages\\one",),
        ("manifest.json",),
        ("pages/1.png", "pages/1.png"),
    ],
)
def test_rejects_unsafe_or_duplicate_asset_paths(tmp_path: Path, paths: tuple[str, ...]) -> None:
    """Untrusted asset paths must not escape staging or overwrite a metadata record."""
    from domain.models.evidence import BinaryAsset

    source = tmp_path / "source.pdf"
    _source(source)
    extraction = PypdfDocumentParser().parse(source)
    extraction = replace(extraction, assets=tuple(BinaryAsset(path, b"x") for path in paths))
    repository = FilesystemEvidenceRepository(tmp_path / "output", extraction.parser)
    with pytest.raises(EvidencePublicationError):
        repository.publish(extraction)
    assert not (tmp_path / "output" / extraction.manifest.sha256 / extraction.parser).exists()


def test_original_bytes_and_image_references_are_validated(tmp_path: Path) -> None:
    """An image link without its asset or a different original cannot become evidence."""
    from domain.models.evidence import BinaryAsset

    source = tmp_path / "source.pdf"
    _source(source)
    base = PypdfDocumentParser().parse(source)
    repository = FilesystemEvidenceRepository(tmp_path / "output", base.parser)
    with pytest.raises(EvidencePublicationError, match="original"):
        repository.publish(replace(base, assets=(BinaryAsset("original.pdf", b"wrong"),)))
    with pytest.raises(EvidencePublicationError, match="image"):
        repository.publish(replace(base, pages=(replace(base.pages[0], image_path="missing.png"),)))


def test_failed_asset_write_never_exposes_complete_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An asset write error must remove staging and leave no published metadata."""
    from domain.models.evidence import BinaryAsset

    source = tmp_path / "source.pdf"
    original = _source(source)
    base = PypdfDocumentParser().parse(source)
    extraction = replace(base, assets=(BinaryAsset("original.pdf", original),))
    repository = FilesystemEvidenceRepository(tmp_path / "output", base.parser)
    write_bytes = Path.write_bytes

    def fail_original(path: Path, data: bytes) -> int:
        if path.name == "original.pdf":
            raise OSError("asset disk full")
        return write_bytes(path, data)

    monkeypatch.setattr(Path, "write_bytes", fail_original)
    with pytest.raises(OSError, match="asset disk full"):
        repository.publish(extraction)
    parent = tmp_path / "output" / base.manifest.sha256
    assert not list(parent.iterdir())


def test_get_rejects_corrupt_or_unlisted_asset_bytes(tmp_path: Path) -> None:
    """A page record must not be returned when its immutable visual evidence is corrupt."""
    from domain.models.evidence import BinaryAsset

    source = tmp_path / "source.pdf"
    original = _source(source)
    base = PypdfDocumentParser().parse(source)
    page = replace(base.pages[0], image_path="pages/1.png")
    extraction = replace(
        base,
        pages=(page,),
        assets=(
            BinaryAsset("original.pdf", original),
            BinaryAsset("pages/1.png", b"png-bytes"),
        ),
    )
    repository = FilesystemEvidenceRepository(tmp_path / "output", base.parser)
    published = repository.publish(extraction)

    (published / "pages/1.png").write_bytes(b"corrupt")
    with pytest.raises(EvidenceNotFoundError, match="inconsistent"):
        repository.get(page.evidence_id)

    (published / "pages/1.png").write_bytes(b"png-bytes")
    (published / "unlisted.bin").write_bytes(b"unexpected")
    with pytest.raises(EvidenceNotFoundError, match="inconsistent"):
        repository.get(page.evidence_id)


@pytest.mark.parametrize("field", ["text", "regions", "elements"])
def test_get_rejects_modified_canonical_page_metadata(tmp_path: Path, field: str) -> None:
    """Page text, geometry, and elements must be hash-bound before evidence is returned."""
    from domain.models.evidence import BinaryAsset, ElementEvidence

    source = tmp_path / "source.pdf"
    original = _source(source)
    base = PypdfDocumentParser().parse(source)
    element = ElementEvidence(
        element_id=f"{base.manifest.document_id}:element:texts:0",
        kind="text",
        text="Original element",
        section=None,
        content_layer="body",
        regions=((1.0, 2.0, 10.0, 12.0),),
    )
    page = replace(base.pages[0], elements=(element,), regions=element.regions)
    extraction = replace(base, pages=(page,), assets=(BinaryAsset("original.pdf", original),))
    repository = FilesystemEvidenceRepository(tmp_path / "output", base.parser)
    published = repository.publish(extraction)
    record = json.loads((published / "pages.jsonl").read_text())
    if field == "text":
        record["text"] = "tampered"
    elif field == "regions":
        record["regions"] = [[20.0, 20.0, 30.0, 30.0]]
    else:
        record["elements"][0]["text"] = "tampered element"
    (published / "pages.jsonl").write_text(json.dumps(record) + "\n")

    with pytest.raises(EvidenceNotFoundError, match="inconsistent"):
        repository.get(page.evidence_id)


def test_get_rejects_modified_extraction_metadata(tmp_path: Path) -> None:
    """Warnings and asset declarations are canonical metadata, not mutable sidecars."""
    from domain.models.evidence import BinaryAsset

    source = tmp_path / "source.pdf"
    original = _source(source)
    base = PypdfDocumentParser().parse(source)
    extraction = replace(base, assets=(BinaryAsset("original.pdf", original),))
    repository = FilesystemEvidenceRepository(tmp_path / "output", base.parser)
    published = repository.publish(extraction)
    metadata = json.loads((published / "extraction.json").read_text())
    metadata["warnings"].append("tampered warning")
    (published / "extraction.json").write_text(json.dumps(metadata) + "\n")

    with pytest.raises(EvidenceNotFoundError, match="inconsistent"):
        repository.get(base.pages[0].evidence_id)


def test_get_rejects_asset_symlink_before_reading_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A symlink must be rejected before its target bytes can cross the trust boundary."""
    from domain.models.evidence import BinaryAsset

    source = tmp_path / "source.pdf"
    original = _source(source)
    base = PypdfDocumentParser().parse(source)
    extraction = replace(base, assets=(BinaryAsset("original.pdf", original),))
    repository = FilesystemEvidenceRepository(tmp_path / "output", base.parser)
    published = repository.publish(extraction)
    asset = published / "original.pdf"
    target = tmp_path / "outside.pdf"
    target.write_bytes(original)
    asset.unlink()
    asset.symlink_to(target)
    read_bytes = Path.read_bytes

    def reject_symlink_read(path: Path) -> bytes:
        if path.is_symlink():
            raise AssertionError("symlink bytes were read")
        return read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", reject_symlink_read)
    with pytest.raises(EvidenceNotFoundError, match="inconsistent"):
        repository.get(base.pages[0].evidence_id)


def test_same_bytes_with_different_filenames_share_one_publication(tmp_path: Path) -> None:
    """A source alias must not make content-addressed evidence conflict with itself."""
    first = tmp_path / "a.pdf"
    data = _source(first)
    second = tmp_path / "b.pdf"
    second.write_bytes(data)
    first_extraction = PypdfDocumentParser().parse(first)
    second_extraction = PypdfDocumentParser().parse(second)
    repository = FilesystemEvidenceRepository(tmp_path / "output", first_extraction.parser)

    published = repository.publish(first_extraction)

    assert repository.publish(second_extraction) == published
    assert repository.get(second_extraction.pages[0].evidence_id) == second_extraction.pages[0]
    stored = json.loads((published / "manifest.json").read_text())
    assert stored["filename"] == f"{first_extraction.manifest.sha256}.pdf"


# --------------------------------------------------------------------------
# test_ingestion_runner
# --------------------------------------------------------------------------


DOCUMENT_HASH = "b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344"


def _extraction() -> Extraction:
    return Extraction(
        manifest=DocumentManifest(
            document_id=f"sha256:{DOCUMENT_HASH}",
            sha256=DOCUMENT_HASH,
            filename="Manual-cide-ascide-y-cicos.pdf",
            page_count=111,
        ),
        pages=(),
        parser="pypdf-6.16.2",
        warnings=(),
    )


@dataclass
class FakeIndexer:
    calls: int = 0

    async def __call__(self, *, document_hash: str, parser: str) -> IndexBuildResult:
        self.calls += 1
        assert document_hash == DOCUMENT_HASH
        assert parser == "pypdf"
        return IndexBuildResult(collection="allianz-test", chunk_count=118)


def test_runner_reports_real_stages_and_publishes_index(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "Manual-cide-ascide-y-cicos.pdf"
    source.write_bytes(b"manual")
    monkeypatch.setattr("application.services.ingestion_runner._sha256", lambda _: DOCUMENT_HASH)
    store = IngestionJobStore(tmp_path / "job.json")
    indexer = FakeIndexer()

    def inspect_and_extract(path: Path) -> Extraction:
        assert path == source
        return _extraction()

    job = store.start()
    runner = IngestionRunner(
        store=store,
        source=source,
        expected_hash=DOCUMENT_HASH,
        inspect_and_extract=inspect_and_extract,
        publish_index=indexer,
    )

    import asyncio

    asyncio.run(runner.run(job.job_id))
    result = store.load().last_job
    assert result is not None
    assert result.status == "succeeded"
    assert result.pages == 111
    assert result.chunks == 118
    assert [event.stage for event in result.events] == [
        "verifying_manual",
        "extracting_evidence",
        "publishing_index",
        "published_index",
    ]
    assert indexer.calls == 1


def test_runner_rejects_an_unexpected_manual_hash_without_indexing(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "manual.pdf"
    source.write_bytes(b"not-the-manual")
    monkeypatch.setattr("application.services.ingestion_runner._sha256", lambda _: DOCUMENT_HASH)
    store = IngestionJobStore(tmp_path / "job.json")
    indexer = FakeIndexer()

    def inspect_and_extract(path: Path) -> Extraction:
        return Extraction(
            manifest=DocumentManifest("sha256:wrong", "0" * 64, path.name, 1),
            pages=(),
            parser="pypdf-6.16.2",
            warnings=(),
        )

    job = store.start()
    runner = IngestionRunner(
        store=store,
        source=source,
        expected_hash=DOCUMENT_HASH,
        inspect_and_extract=inspect_and_extract,
        publish_index=indexer,
    )

    import asyncio

    asyncio.run(runner.run(job.job_id))
    result = store.load().last_job
    assert result is not None
    assert result.status == "failed"
    assert result.error == "El manual no coincide con la fuente verificada."
    assert indexer.calls == 0


# --------------------------------------------------------------------------
# test_ingestion_jobs
# --------------------------------------------------------------------------


def test_store_starts_and_persists_one_running_job(tmp_path) -> None:
    store = IngestionJobStore(tmp_path / "ingestion.json")

    initial = store.load()
    assert isinstance(initial, IngestionSnapshot)
    assert initial.active_job is None

    job = store.start()
    assert job.status == "running"
    assert job.stage == "verifying_manual"

    reloaded = IngestionJobStore(tmp_path / "ingestion.json").load()
    assert reloaded.active_job is not None
    assert reloaded.active_job.job_id == job.job_id

    with pytest.raises(IngestionAlreadyRunning):
        store.start()


def test_store_appends_public_event_and_marks_terminal_job(tmp_path) -> None:
    store = IngestionJobStore(tmp_path / "ingestion.json")
    job = store.start()
    event = IngestionEvent(
        event_id="evt-1",
        job_id=job.job_id,
        timestamp=datetime.now(UTC),
        stage="extracting_evidence",
        status="running",
        data={"pages": 111},
    )

    store.append_event(job.job_id, event)
    completed = store.update(
        job.job_id,
        status="succeeded",
        stage="published_index",
        pages=111,
        chunks=118,
        collection="allianz-test",
    )

    assert completed.status == "succeeded"
    assert completed.events == (event,)
    assert store.load().active_job is None
    assert store.load().last_job == completed
