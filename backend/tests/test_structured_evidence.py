"""Publication checks use real bytes so incomplete or corrupt evidence is observable."""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from pypdf import PdfWriter

from infrastructure.adapters.outbound.document_parser.pypdf_parser import PypdfDocumentParser
from infrastructure.adapters.outbound.evidence_repository.filesystem_repository import (
    EvidenceNotFoundError,
    EvidencePublicationError,
    FilesystemEvidenceRepository,
)


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
