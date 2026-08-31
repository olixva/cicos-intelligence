"""Immutable evidence extracted from a source document."""

from dataclasses import dataclass

from domain.models.document import DocumentManifest


@dataclass(frozen=True, slots=True)
class BinaryAsset:
    """Immutable bytes at a deterministic path relative to the publication directory."""

    path: str
    data: bytes


@dataclass(frozen=True, slots=True)
class ElementEvidence:
    """One source element; regions use visible page points with top-left origin."""

    element_id: str
    kind: str
    text: str
    section: str | None
    content_layer: str
    regions: tuple[tuple[float, float, float, float], ...]


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
    elements: tuple[ElementEvidence, ...] = ()
    width: float | None = None
    height: float | None = None


@dataclass(frozen=True, slots=True)
class Extraction:
    """The immutable result produced by one named document parser."""

    manifest: DocumentManifest
    pages: tuple[PageEvidence, ...]
    parser: str
    warnings: tuple[str, ...]
    assets: tuple[BinaryAsset, ...] = ()
