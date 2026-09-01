"""Real-source conversion; opt in explicitly because local models take minutes."""

import os
from pathlib import Path

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, RectangleObject


def _cropped_rotated_text_pages(path: Path) -> None:
    writer = PdfWriter()
    for rotation in (0, 90, 180, 270):
        page = writer.add_blank_page(width=300, height=200)
        page.cropbox = RectangleObject((50, 30, 250, 130))
        page.rotate(rotation)
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject(
                    {
                        NameObject("/F1"): writer._add_object(  # pyright: ignore[reportPrivateUsage]
                            font
                        )
                    }
                )
            }
        )
        stream = DecodedStreamObject()
        # Crop-local x=20, y=15. PDFium's native boxes retain (50, 30) without normalization.
        stream.set_data(b"BT /F1 20 Tf 70 45 Td (TARGET) Tj ET")
        page[NameObject("/Contents")] = writer._add_object(  # pyright: ignore[reportPrivateUsage]
            stream
        )
    writer.write(path)


def test_cropped_rotated_provenance_uses_visible_page_coordinates(tmp_path: Path) -> None:
    """Crop offsets or unbaked rotation would put these regions outside the visible target areas."""
    from infrastructure.adapters.outbound.document_parser.docling_parser import DoclingParser

    source = tmp_path / "geometry.pdf"
    _cropped_rotated_text_pages(source)
    extracted = DoclingParser().parse(source)

    assert [(page.width, page.height) for page in extracted.pages] == [
        (200.0, 100.0),
        (100.0, 200.0),
        (200.0, 100.0),
        (100.0, 200.0),
    ]
    expected_centers = ((60, 78), (22, 60), (140, 22), (78, 140))
    for page, (expected_x, expected_y) in zip(extracted.pages, expected_centers, strict=True):
        assert page.width is not None
        assert page.height is not None
        assert page.elements
        left, top, right, bottom = page.elements[0].regions[0]
        assert abs((left + right) / 2 - expected_x) < 8
        assert abs((top + bottom) / 2 - expected_y) < 8
        assert 0 <= left < right <= page.width
        assert 0 <= top < bottom <= page.height
    assert any(asset.path == "layout-input.pdf" for asset in extracted.assets)


def test_real_manual_preserves_inventory_and_reports_scan_review(tmp_path: Path) -> None:
    """Losing pages or presenting the scanned form as trusted text must fail this check."""
    configured = os.environ.get("ALLIANZ_INTEGRATION_PDF")
    if not configured:
        pytest.skip("Set ALLIANZ_INTEGRATION_PDF to execute real 111-page conversion")
    from infrastructure.adapters.outbound.document_parser.docling_parser import DoclingParser
    from infrastructure.adapters.outbound.document_parser.pypdf_parser import PypdfDocumentParser
    from infrastructure.adapters.outbound.evidence_repository.filesystem_repository import (
        FilesystemEvidenceRepository,
    )

    source = Path(configured)
    baseline = PypdfDocumentParser().parse(source)
    extracted = DoclingParser().parse(source)
    assert extracted.manifest == baseline.manifest
    assert extracted.manifest.page_count == 111
    assert extracted.manifest.sha256 == (
        "b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344"
    )
    assert [page.evidence_id for page in extracted.pages] == [
        page.evidence_id for page in baseline.pages
    ]
    assert any(element.kind == "table" for element in extracted.pages[100].elements)
    assert any(
        warning.startswith("Page 32 has little extracted text")
        and "review original image" in warning
        for warning in extracted.warnings
    )
    assert any(
        warning.startswith("Page 32 contains picture evidence")
        and "review original image" in warning
        for warning in extracted.warnings
    )
    assert any(
        warning.startswith("Page 101 contains an unverified table")
        and "before using it as rules" in warning
        for warning in extracted.warnings
    )
    repository = FilesystemEvidenceRepository(tmp_path / "evidence", extracted.parser)
    published = repository.publish(extracted)
    assert (published / "original.pdf").read_bytes() == source.read_bytes()
    for page in extracted.pages:
        assert page.image_path is not None
        assert (published / page.image_path).read_bytes().startswith(b"\x89PNG")
    assert repository.get(extracted.pages[100].evidence_id) == extracted.pages[100]
    assert repository.publish(extracted) == published
