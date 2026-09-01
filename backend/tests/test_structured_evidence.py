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
