"""Application composition root."""

from pathlib import Path

from application.ports.inbound.ingest_document import IngestDocument
from application.ports.inbound.inspect_manual import InspectManual
from application.use_cases.ingest_document_use_case import IngestDocumentUseCase
from application.use_cases.inspect_manual_use_case import InspectManualUseCase
from infrastructure.adapters.outbound.document_parser.pypdf_parser import PypdfDocumentParser
from infrastructure.adapters.outbound.evidence_repository.filesystem_repository import (
    FilesystemEvidenceRepository,
)
from infrastructure.adapters.outbound.source_inspector.pypdf_source_inspector import (
    PypdfSourceInspector,
)


def build_inspect_manual() -> InspectManual:
    """Build the manual-inspection use case with its PDF adapter."""
    return InspectManualUseCase(inspector=PypdfSourceInspector())


def build_ingest_document(output: Path, parser: str = "pypdf") -> IngestDocument:
    """Build baseline ingestion with pypdf evidence stored under its exact version."""
    if parser != "pypdf":
        raise ValueError(f"Unsupported parser: {parser}")
    document_parser = PypdfDocumentParser()
    return IngestDocumentUseCase(
        parser=document_parser,
        repository=FilesystemEvidenceRepository(output, document_parser.parser),
    )
