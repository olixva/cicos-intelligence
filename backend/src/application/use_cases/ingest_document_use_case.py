"""Use case for extraction and immutable publication of page evidence."""

from dataclasses import dataclass
from pathlib import Path

from application.ports.outbound.document_parser import DocumentParser
from application.ports.outbound.evidence_repository import EvidenceRepository
from domain.models.evidence import Extraction


@dataclass(frozen=True, slots=True)
class IngestDocumentUseCase:
    """Parse a document then publish exactly the resulting evidence."""

    parser: DocumentParser
    repository: EvidenceRepository

    def execute(self, source: Path) -> Extraction:
        """Publish evidence derived from the same bytes used to identify it."""
        extraction = self.parser.parse(source)
        self.repository.publish(extraction)
        return extraction
