"""Immutable representations and errors for inspected source documents."""

from dataclasses import dataclass


class SourceInspectionError(Exception):
    """Raised when a source document cannot be safely inspected."""


class SourceIntegrityError(Exception):
    """Raised when a source document does not match its expected identity."""


@dataclass(frozen=True, slots=True)
class DocumentManifest:
    """Identity and basic structural information for a source document."""

    document_id: str
    sha256: str
    filename: str
    page_count: int
