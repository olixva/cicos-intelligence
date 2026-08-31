"""Known PDF geometry, independent of neural layout predictions."""

from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject, RectangleObject


def colored_page(path: Path, rotation: int) -> None:
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=200)
    page.cropbox = RectangleObject((50, 30, 250, 130))
    page.rotate(rotation)
    stream = DecodedStreamObject()
    # A red box at crop-local x=20..40, y=10..30 (PDF bottom-left coordinates).
    stream.set_data(b"1 0 0 rg 70 40 20 20 re f")
    page[NameObject("/Contents")] = writer._add_object(stream)  # pyright: ignore[reportPrivateUsage]
    writer.write(path)


@pytest.mark.parametrize(
    ("rotation", "size", "red_center"),
    [
        (0, (400, 200), (60, 160)),
        (90, (200, 400), (40, 60)),
        (180, (400, 200), (340, 40)),
        (270, (200, 400), (160, 340)),
    ],
)
def test_renderer_uses_visible_crop_and_rotation(
    tmp_path: Path,
    rotation: int,
    size: tuple[int, int],
    red_center: tuple[int, int],
) -> None:
    """Ignoring a crop offset or applying /Rotate twice moves the red reference box."""
    from infrastructure.adapters.outbound.document_parser.page_renderer import render_page

    source = tmp_path / "geometry.pdf"
    colored_page(source, rotation)
    result = render_page(source, 1, tmp_path / "render.png")
    with Image.open(result) as image:
        assert image.size == size
        assert image.convert("RGB").getpixel(red_center) == (255, 0, 0)
        assert image.convert("RGB").getpixel((0, 0)) == (255, 255, 255)


@pytest.mark.parametrize("number", [0, -1, 2])
def test_renderer_rejects_nonexistent_physical_pages(tmp_path: Path, number: int) -> None:
    """PDF page zero must not accidentally select the last page through negative indexing."""
    from infrastructure.adapters.outbound.document_parser.page_renderer import render_page

    source = tmp_path / "geometry.pdf"
    colored_page(source, 0)
    with pytest.raises(ValueError, match="page"):
        render_page(source, number, tmp_path / "render.png")


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_layout_normalization_keeps_visible_pixels_and_zeroes_crop_offsets(
    tmp_path: Path,
    rotation: int,
) -> None:
    """Layout input normalization must not move crop-local content or retain offsets."""
    from io import BytesIO

    from pypdf import PdfReader

    from infrastructure.adapters.outbound.document_parser.page_renderer import (
        normalize_layout_pdf,
        render_page_bytes,
    )

    source = tmp_path / "geometry.pdf"
    colored_page(source, rotation)
    original = source.read_bytes()
    normalized = normalize_layout_pdf(original)
    page = PdfReader(BytesIO(normalized)).pages[0]
    assert page.rotation == 0
    assert page.cropbox.left == page.cropbox.bottom == 0
    assert render_page_bytes(normalized, 1) == render_page_bytes(original, 1)
