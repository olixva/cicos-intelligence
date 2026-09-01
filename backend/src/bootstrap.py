"""Application composition root."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from application.ports.inbound.ingest_document import IngestDocument
from application.ports.inbound.inspect_manual import InspectManual
from application.use_cases.build_retrieval_index_use_case import (
    BuildRetrievalIndexUseCase,
    IndexBuildResult,
)
from application.use_cases.ingest_document_use_case import IngestDocumentUseCase
from application.use_cases.inspect_manual_use_case import InspectManualUseCase
from infrastructure.adapters.outbound.document_parser.pypdf_parser import PypdfDocumentParser
from infrastructure.adapters.outbound.evidence_repository.filesystem_repository import (
    FilesystemEvidenceRepository,
)
from infrastructure.adapters.outbound.source_inspector.pypdf_source_inspector import (
    PypdfSourceInspector,
)

if TYPE_CHECKING:
    from fastapi import FastAPI


def build_inspect_manual() -> InspectManual:
    """Build the manual-inspection use case with its PDF adapter."""
    return InspectManualUseCase(inspector=PypdfSourceInspector())


def build_ingest_document(output: Path, parser: str = "pypdf") -> IngestDocument:
    """Build an explicit parser without loading optional ingestion dependencies by default."""
    if parser == "pypdf":
        document_parser = PypdfDocumentParser()
    elif parser == "docling":
        from infrastructure.adapters.outbound.document_parser.docling_parser import DoclingParser

        document_parser = DoclingParser()
    else:
        raise ValueError(f"Unsupported parser: {parser}")
    return IngestDocumentUseCase(
        parser=document_parser,
        repository=FilesystemEvidenceRepository(output, document_parser.parser),
    )


async def build_and_publish_retrieval_index(
    *,
    document_hash: str,
    evidence_root: Path,
    parser: str,
    profile_name: str,
    qdrant_url: str,
) -> IndexBuildResult:
    """Compose the local Qdrant and OpenAI adapters for a verified index publication."""
    from qdrant_client import AsyncQdrantClient

    from infrastructure.adapters.outbound.embedding_provider.openai_embedding_provider import (
        OpenAIEmbeddingProvider,
    )
    from infrastructure.adapters.outbound.retriever.index_builder import QdrantIndexBuilder
    from infrastructure.adapters.outbound.retriever.qdrant_retriever import FastEmbedBm25Encoder
    from infrastructure.config.profiles import load_profile

    profile = load_profile(profile_name, _profile_catalog_dir())
    client = AsyncQdrantClient(url=qdrant_url)
    try:
        publisher = QdrantIndexBuilder(
            client=client,
            embedding_provider=OpenAIEmbeddingProvider(
                model=profile.embedding_model,
                dimensions=profile.dimensions,
            ),
            sparse_encoder=FastEmbedBm25Encoder(language=profile.lexical_language),
            active_alias="allianz-manual-active",
        )
        return await BuildRetrievalIndexUseCase(
            evidence_repository=FilesystemEvidenceRepository(evidence_root, parser),
            publisher=publisher,
            profile=profile,
        ).execute(document_hash=document_hash, resolved_parser=parser)
    finally:
        await client.close()


def _profile_catalog_dir() -> Path:
    """Locate the project-owned strict profile catalog outside importable source modules."""
    return Path(__file__).parent.parent / "configs"


def build_api() -> FastAPI:
    """Build the local HTTP adapter through its dependency-aware factory."""

    from infrastructure.adapters.inbound.api.app import create_app

    return create_app()
