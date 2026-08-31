"""pypdf-backed implementation of source document inspection."""

from hashlib import sha256
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from domain.models.document import DocumentManifest, SourceInspectionError


class PypdfSourceInspector:
    """Inspect one readable, unencrypted PDF without modifying it."""

    def inspect(self, source: Path) -> DocumentManifest:
        """Read document bytes once and derive a minimal manifest from them."""
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

        return DocumentManifest(
            document_id=f"sha256:{digest}",
            sha256=digest,
            filename=source.name,
            page_count=page_count,
        )
