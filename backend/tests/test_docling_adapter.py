"""Test our projection of real Docling models; neural conversion is the slow boundary."""

import json
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.base_models import ConversionStatus, InputFormat
from docling.datamodel.document import ConversionResult, InputDocument
from docling.document_converter import DocumentConverter
from docling_core.types.doc.base import BoundingBox, CoordOrigin, Size
from docling_core.types.doc.common.content_layer import ContentLayer
from docling_core.types.doc.common.reference import ProvenanceItem
from docling_core.types.doc.document import DoclingDocument
from docling_core.types.doc.labels import DocItemLabel
from pypdf import PdfWriter

from infrastructure.adapters.outbound.document_parser.model_artifacts import ModelBundle


def _two_pages(path: Path) -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=100)
    writer.add_blank_page(width=200, height=100)
    writer.write(path)
    return path.read_bytes()


def test_projection_retains_furniture_geometry_sections_and_missing_pages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_model_bundle: ModelBundle,
) -> None:
    """Dropping furniture, trusting missing OCR, or double-flipping display boxes loses evidence."""
    from infrastructure.adapters.outbound.document_parser.docling_parser import DoclingParser

    source = tmp_path / "source.pdf"
    original = _two_pages(source)
    document = DoclingDocument(name="Fixture")
    document.add_page(1, Size(width=200, height=100))
    provenance = ProvenanceItem(
        page_no=1,
        charspan=(0, 8),
        bbox=BoundingBox(l=10, t=80, r=90, b=60, coord_origin=CoordOrigin.BOTTOMLEFT),
    )
    document.add_heading("Coverage", prov=provenance)
    document.add_text(label=DocItemLabel.TEXT, text="Conditions", prov=provenance)
    document.add_text(
        label=DocItemLabel.FOOTNOTE,
        text="Critical note",
        prov=provenance,
        content_layer=ContentLayer.FURNITURE,
    )
    input_doc = InputDocument(
        path_or_stream=BytesIO(original),
        format=InputFormat.PDF,
        backend=PyPdfiumDocumentBackend,
        filename=source.name,
    )
    result = ConversionResult(
        input=input_doc, document=document, status=ConversionStatus.PARTIAL_SUCCESS
    )

    def converted(*args: Any, **kwargs: Any) -> ConversionResult:
        source.write_bytes(b"changed after snapshot")
        return result

    monkeypatch.setattr(DocumentConverter, "convert", converted)
    extraction = DoclingParser(model_bundle=fake_model_bundle).parse(source)
    assert [page.pdf_page for page in extraction.pages] == [1, 2]
    page = extraction.pages[0]
    assert "Critical note" in page.text
    assert len(page.elements) == 3
    note = next(element for element in page.elements if element.kind == "footnote")
    assert note.section == "Coverage"
    assert note.content_layer == "furniture"
    assert note.regions == ((10.0, 20.0, 90.0, 40.0),)
    assert note.element_id.startswith(f"{extraction.manifest.document_id}:element:")
    assert (page.width, page.height) == (200.0, 100.0)
    assert any("Page 2" in warning and "missing" in warning for warning in extraction.warnings)
    assert any("partial_success" in warning for warning in extraction.warnings)
    assert (
        next(asset.data for asset in extraction.assets if asset.path == "original.pdf") == original
    )
    assert all(not asset.path.startswith(str(tmp_path)) for asset in extraction.assets)


def test_ocr_failure_is_declared_without_dropping_original_pages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_model_bundle: ModelBundle,
) -> None:
    """A conversion exception must retain each rendered page and an explicit failure warning."""
    from infrastructure.adapters.outbound.document_parser.docling_parser import DoclingParser

    source = tmp_path / "source.pdf"
    original = _two_pages(source)

    def failed(*args: Any, **kwargs: Any) -> ConversionResult:
        raise RuntimeError("OCR engine unavailable")

    monkeypatch.setattr(DocumentConverter, "convert", failed)
    extraction = DoclingParser(model_bundle=fake_model_bundle).parse(source)
    assert len(extraction.pages) == 2
    assert all(page.image_path for page in extraction.pages)
    assert any("OCR engine unavailable" in warning for warning in extraction.warnings)
    assert any("failed" in warning for warning in extraction.warnings)
    assert (
        next(asset.data for asset in extraction.assets if asset.path == "original.pdf") == original
    )


def test_furniture_uses_the_section_active_on_its_own_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_model_bundle: ModelBundle
) -> None:
    """Furniture iterated after the body must not inherit the document's final section."""
    from infrastructure.adapters.outbound.document_parser.docling_parser import DoclingParser

    source = tmp_path / "source.pdf"
    original = _two_pages(source)
    document = DoclingDocument(name="Fixture")
    for number in (1, 2):
        document.add_page(number, Size(width=200, height=100))
    first = ProvenanceItem(
        page_no=1,
        charspan=(0, 8),
        bbox=BoundingBox(l=10, t=80, r=90, b=60, coord_origin=CoordOrigin.BOTTOMLEFT),
    )
    second = first.model_copy(update={"page_no": 2})
    document.add_heading("Coverage", prov=first)
    document.add_text(
        label=DocItemLabel.PAGE_FOOTER,
        text="Page one",
        prov=first,
        content_layer=ContentLayer.FURNITURE,
        parent=document.__dict__["furniture"],
    )
    document.add_heading("Exclusions", prov=second)
    input_doc = InputDocument(
        path_or_stream=BytesIO(original),
        format=InputFormat.PDF,
        backend=PyPdfiumDocumentBackend,
        filename=source.name,
    )
    converted = ConversionResult(
        input=input_doc, document=document, status=ConversionStatus.SUCCESS
    )

    def convert(*args: Any, **kwargs: Any) -> ConversionResult:
        return converted

    monkeypatch.setattr(DocumentConverter, "convert", convert)

    extraction = DoclingParser(model_bundle=fake_model_bundle).parse(source)

    footer = next(
        element for element in extraction.pages[0].elements if element.kind == "page_footer"
    )
    assert footer.section == "Coverage"


def test_configuration_records_effective_ocr_backend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_model_bundle: ModelBundle
) -> None:
    """Changing the RapidOCR runtime backend must change persisted parser configuration."""
    from infrastructure.adapters.outbound.document_parser.docling_parser import DoclingParser

    source = tmp_path / "source.pdf"
    original = _two_pages(source)
    document = DoclingDocument(name="Fixture")
    converted = ConversionResult(
        input=InputDocument(
            path_or_stream=BytesIO(original),
            format=InputFormat.PDF,
            backend=PyPdfiumDocumentBackend,
            filename=source.name,
        ),
        document=document,
        status=ConversionStatus.SUCCESS,
    )

    def convert(*args: Any, **kwargs: Any) -> ConversionResult:
        return converted

    monkeypatch.setattr(DocumentConverter, "convert", convert)

    extraction = DoclingParser(model_bundle=fake_model_bundle).parse(source)
    configuration = json.loads(
        next(asset.data for asset in extraction.assets if asset.path == "configuration.json")
    )

    assert configuration["ocr"] == {
        "backend": "torch",
        "engine": "RapidOCR",
        "languages": ["latin"],
    }


def test_source_alias_does_not_change_docling_assets_or_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_model_bundle: ModelBundle,
) -> None:
    """Docling's raw exports must use content identity rather than the caller's filename."""
    from infrastructure.adapters.outbound.document_parser.docling_parser import DoclingParser
    from infrastructure.adapters.outbound.evidence_repository.filesystem_repository import (
        FilesystemEvidenceRepository,
    )

    first = tmp_path / "a.pdf"
    original = _two_pages(first)
    second = tmp_path / "b.pdf"
    second.write_bytes(original)

    def convert(stream: Any, **kwargs: Any) -> ConversionResult:
        document = DoclingDocument(name=Path(stream.name).stem)
        return ConversionResult(
            input=InputDocument(
                path_or_stream=BytesIO(original),
                format=InputFormat.PDF,
                backend=PyPdfiumDocumentBackend,
                filename=stream.name,
            ),
            document=document,
            status=ConversionStatus.SUCCESS,
        )

    monkeypatch.setattr(DocumentConverter, "convert", convert)
    parser = DoclingParser(model_bundle=fake_model_bundle)

    first_extraction = parser.parse(first)
    second_extraction = parser.parse(second)

    assert first_extraction.manifest.filename == "a.pdf"
    assert second_extraction.manifest.filename == "b.pdf"
    assert first_extraction.assets == second_extraction.assets
    repository = FilesystemEvidenceRepository(tmp_path / "evidence", parser.parser)
    assert repository.publish(first_extraction) == repository.publish(second_extraction)
