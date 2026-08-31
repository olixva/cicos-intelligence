"""Shared validation and byte-bound opening for untrusted PDF sources."""

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from domain.models.document import DocumentManifest, SourceInspectionError


@dataclass(frozen=True, slots=True)
class OpenPdfSource:
    """A validated PDF reader and manifest both derived from one byte sequence."""

    manifest: DocumentManifest
    reader: PdfReader
    data: bytes = b""


def open_pdf_source(source: Path) -> OpenPdfSource:
    """Read once, validate PDF structure, and retain the reader over those bytes."""
    try:
        data = source.read_bytes()
    except OSError as error:
        raise SourceInspectionError(f"Unable to read source: {source}") from error

    digest = sha256(data).hexdigest()
    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            raise SourceInspectionError("Encrypted PDF sources are not supported")
        page_count = len(reader.pages)
    except PdfReadError as error:
        raise SourceInspectionError("The source is not a readable PDF") from error

    if page_count == 0:
        raise SourceInspectionError("PDF sources must contain at least one page")

    return OpenPdfSource(
        manifest=DocumentManifest(
            document_id=f"sha256:{digest}",
            sha256=digest,
            filename=source.name,
            page_count=page_count,
        ),
        reader=reader,
        data=data,
    )
