"""Build an index only from complete published evidence and a strict retrieval profile."""

from dataclasses import dataclass

from application.models.retrieval import (
    FixedChunkingConfig,
    RetrievalProfile,
    SectionChunkingConfig,
)
from application.ports.outbound.evidence_repository import EvidenceRepository
from application.ports.outbound.index_publisher import IndexPublisher
from application.services.chunking import chunk_fixed, chunk_sections


@dataclass(frozen=True, slots=True)
class IndexBuildResult:
    """Safe metadata returned after one atomically published index build."""

    collection: str
    chunk_count: int


class BuildRetrievalIndexUseCase:
    """Derive chunks and a signature from a verified document publication."""

    def __init__(
        self,
        evidence_repository: EvidenceRepository,
        publisher: IndexPublisher,
        profile: RetrievalProfile,
    ) -> None:
        self._evidence_repository = evidence_repository
        self._publisher = publisher
        self._profile = profile

    async def execute(self, *, document_hash: str, resolved_parser: str) -> IndexBuildResult:
        """Publish chunks only when the selected profile matches the evidence parser."""
        if not resolved_parser.startswith(f"{self._profile.parser}-"):
            raise ValueError(
                "retrieval profile parser does not match the published evidence parser"
            )
        pages = self._evidence_repository.get_document_pages(document_hash)
        chunker = self._profile.chunker
        if isinstance(chunker, FixedChunkingConfig):
            chunks = chunk_fixed(pages, chunker.size, chunker.overlap)
        elif isinstance(chunker, SectionChunkingConfig):
            chunks = chunk_sections(pages, chunker.max_size)
        else:
            raise TypeError("unsupported retrieval chunker")
        signature = self._profile.build_index_signature(document_hash, resolved_parser)
        collection = await self._publisher.build_index(chunks, signature)
        return IndexBuildResult(collection=collection, chunk_count=len(chunks))
