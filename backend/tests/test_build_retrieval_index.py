"""The index orchestration must bind chunks to verified source evidence."""

import asyncio
from dataclasses import dataclass
from pathlib import Path

import pytest

from application.models.retrieval import (
    Chunk,
    FixedChunkingConfig,
    IndexSignature,
    RetrievalProfile,
    SectionChunkingConfig,
)
from domain.models.evidence import Extraction, PageEvidence

DOCUMENT_HASH = "a" * 64
PARSER = "docling-2.124.0-pdfium-5.13.0-rapidocr-latin-torch-r2-3d1d1af9689b76cf"


@dataclass
class _Evidence:
    pages: tuple[PageEvidence, ...]
    requested_hash: str | None = None

    def get_document_pages(self, document_hash: str) -> tuple[PageEvidence, ...]:
        self.requested_hash = document_hash
        return self.pages

    def get(self, evidence_id: str) -> PageEvidence:
        return self.pages[0]

    def publish(self, extraction: Extraction) -> Path:
        raise AssertionError("index construction must not publish evidence")


@dataclass
class _Publisher:
    collection: str = "allianz-active-collection"
    chunks: tuple[Chunk, ...] = ()
    signature: IndexSignature | None = None

    async def build_index(self, chunks: tuple[Chunk, ...], signature: IndexSignature) -> str:
        self.chunks = chunks
        self.signature = signature
        return self.collection


def _page() -> PageEvidence:
    return PageEvidence(
        evidence_id=f"sha256:{DOCUMENT_HASH}:page:1",
        document_hash=DOCUMENT_HASH,
        pdf_page=1,
        text="Cobertura de asistencia en viaje.",
        printed_label="1",
        image_path=None,
        regions=(),
        elements=(),
        width=None,
        height=None,
    )


def test_builds_structured_chunks_from_verified_pages_and_returns_collection() -> None:
    from application.use_cases.build_retrieval_index_use_case import BuildRetrievalIndexUseCase

    evidence = _Evidence((_page(),))
    publisher = _Publisher()
    profile = RetrievalProfile(
        parser="docling",
        chunker=SectionChunkingConfig(max_size=1200),
        embedding_model="text-embedding-3-small",
        dimensions=1536,
        lexical_language="spanish",
    )

    result = asyncio.run(
        BuildRetrievalIndexUseCase(evidence, publisher, profile).execute(
            document_hash=DOCUMENT_HASH,
            resolved_parser=PARSER,
        )
    )

    assert result.collection == "allianz-active-collection"
    assert result.chunk_count == 1
    assert evidence.requested_hash == DOCUMENT_HASH
    assert publisher.chunks[0].evidence_ids == (_page().evidence_id,)
    assert publisher.signature == profile.build_index_signature(DOCUMENT_HASH, PARSER)


def test_rejects_a_profile_that_does_not_match_the_published_parser() -> None:
    from application.use_cases.build_retrieval_index_use_case import BuildRetrievalIndexUseCase

    profile = RetrievalProfile(
        parser="pypdf",
        chunker=FixedChunkingConfig(size=1200, overlap=200),
        embedding_model="text-embedding-3-small",
        dimensions=1536,
        lexical_language="spanish",
    )
    with pytest.raises(ValueError, match="parser"):
        asyncio.run(
            BuildRetrievalIndexUseCase(_Evidence((_page(),)), _Publisher(), profile).execute(
                document_hash=DOCUMENT_HASH,
                resolved_parser=PARSER,
            )
        )


def test_profile_catalog_is_packaged_next_to_the_backend_project() -> None:
    from bootstrap import profile_catalog_dir

    catalog = profile_catalog_dir()

    assert (catalog / "structured.yaml").is_file()
    assert (catalog / "baseline.yaml").is_file()
