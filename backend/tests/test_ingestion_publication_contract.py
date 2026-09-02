"""Contract tests for the immutable ingestion publication.

These tests formalize the unified publication contract so that both
pypdf and Docling produce interchangeable directories, and so that
reconstructing a publication from the original PDF is reproducible.

See plan T2: \"Publicaciones de ingestión inmutables y comparables\".
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from pypdf import PdfWriter

from domain.models.evidence import BinaryAsset, Extraction, PageEvidence
from infrastructure.adapters.outbound.document_parser.pypdf_parser import PypdfDocumentParser
from infrastructure.adapters.outbound.evidence_repository.filesystem_repository import (
    FilesystemEvidenceRepository,
)

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
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
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
