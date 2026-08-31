"""Original PDF rendering, independent of Docling's layout and OCR predictions."""

from io import BytesIO
from pathlib import Path
from typing import Protocol, cast

import pypdfium2 as pdfium
from docling.utils.locks import pypdfium2_lock
from PIL.Image import Image


class _PdfBitmap(Protocol):
    def to_pil(self) -> Image: ...

    def close(self) -> None: ...


class _PdfDocumentForms(Protocol):
    def init_forms(self) -> bool: ...


class _RenderablePdfPage(Protocol):
    def render(self, *, scale: int, draw_annots: bool) -> _PdfBitmap: ...


def render_page(source: Path, pdf_page: int, destination: Path) -> Path:
    """Render a 1-based physical page at 144 dpi, respecting its crop and rotation."""
    png, _, _ = render_page_bytes(source.read_bytes(), pdf_page)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(png)
    return destination


def render_page_bytes(data: bytes, pdf_page: int) -> tuple[bytes, float, float]:
    """Render the immutable source snapshot; dimensions are visible PDF points."""
    with pypdfium2_lock, pdfium.PdfDocument(data) as document:
        cast(_PdfDocumentForms, document).init_forms()
        if isinstance(pdf_page, bool) or not 1 <= pdf_page <= len(document):
            raise ValueError("Physical PDF page is outside the document")
        page = document[pdf_page - 1]
        width, height = page.get_size()
        bitmap = cast(_RenderablePdfPage, page).render(scale=2, draw_annots=True)
        try:
            buffer = BytesIO()
            image = bitmap.to_pil()
            image.save(buffer, format="PNG")
            image.close()
            return buffer.getvalue(), width, height
        finally:
            bitmap.close()
            page.close()


def normalize_layout_pdf(data: bytes) -> bytes:
    """Zero crop offsets and bake rotation for layout only; never replace original evidence.

    Docling's PDFium backend expects native text coordinates in a zero-origin page.
    The source is returned unchanged when already in that coordinate frame.
    """
    from pypdf import PdfReader, PdfWriter, Transformation
    from pypdf.generic import RectangleObject

    reader = PdfReader(BytesIO(data))
    if all(
        page.rotation == 0
        and page.cropbox.left == page.cropbox.bottom == 0
        and page.cropbox == page.mediabox
        for page in reader.pages
    ):
        return data
    writer = PdfWriter()
    for source_page in reader.pages:
        page = writer.add_page(source_page)
        page.transfer_rotation_to_content()
        left = max(float(page.cropbox.left), float(page.mediabox.left))
        bottom = max(float(page.cropbox.bottom), float(page.mediabox.bottom))
        right = min(float(page.cropbox.right), float(page.mediabox.right))
        top = min(float(page.cropbox.top), float(page.mediabox.top))
        if right <= left or top <= bottom:
            raise ValueError("PDF crop does not intersect its media box")
        page.add_transformation(Transformation().translate(-left, -bottom))
        visible = RectangleObject((0, 0, right - left, top - bottom))
        page.mediabox = visible
        page.cropbox = visible
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()
