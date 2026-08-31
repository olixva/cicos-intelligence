"""Immutable evidence extracted from a source document."""

from dataclasses import dataclass

from domain.models.document import DocumentManifest


@dataclass(frozen=True, slots=True)
class PageEvidence:
    """All baseline evidence available for one physical PDF page."""

    evidence_id: str
    document_hash: str
    pdf_page: int
    text: str
    printed_label: str | None
    image_path: str | None
    regions: tuple[tuple[float, float, float, float], ...]


@dataclass(frozen=True, slots=True)
class Extraction:
    """The immutable result produced by one named document parser."""

    manifest: DocumentManifest
    pages: tuple[PageEvidence, ...]
    parser: str
    warnings: tuple[str, ...]
