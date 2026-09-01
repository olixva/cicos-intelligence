"""Retrieval contracts against Qdrant's real local execution engine."""

import asyncio
import re
import uuid
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

import pytest
from qdrant_client import AsyncQdrantClient, models
from qdrant_client.http.exceptions import ResponseHandlingException

from application.models.retrieval import Chunk, IndexSignature

DOCUMENT_HASH = "b" * 64
ACTIVE_ALIAS = "technical-fixture-active"
CORPUS = (
    Chunk(
        "chunk-literal",
        "El protocolo ATX registra el parte técnico ZXQ-991 como no autorizado.",
        ("evidence-literal",),
    ),
    Chunk(
        "chunk-weather",
        "La indemnización protege el vehículo frente a tormentas y granizo.",
        ("evidence-weather",),
    ),
    Chunk(
        "chunk-workshop",
        "El taller certifica la reparación de la puerta lateral.",
        ("evidence-workshop",),
    ),
)


class FixtureEmbeddingProvider:
    """Deterministic semantic fixture; it carries no labels from the source manual."""

    async def embed(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        vectors: list[tuple[float, ...]] = []
        for text in texts:
            lowered = text.lower()
            if "meteorológica" in lowered or "tormentas" in lowered or "granizo" in lowered:
                vectors.append((1.0, 0.0, 0.0))
            elif "taller" in lowered or "reparación" in lowered:
                vectors.append((0.0, 1.0, 0.0))
            else:
                vectors.append((0.0, 0.0, 1.0))
        return tuple(vectors)


def _signature() -> IndexSignature:
    return IndexSignature(
        DOCUMENT_HASH,
        "fixture-parser-1",
        "fixture-chunker-1",
        "fixture-embedding-1",
        3,
        "spanish",
    )


async def _build_retriever(tmp_path: Path):  # pyright: ignore[reportMissingReturnType]
    from infrastructure.adapters.outbound.retriever.index_builder import QdrantIndexBuilder
    from infrastructure.adapters.outbound.retriever.qdrant_retriever import (
        FastEmbedBm25Encoder,
        QdrantRetriever,
    )

    client = AsyncQdrantClient(path=str(tmp_path / "qdrant"))
    encoder = FastEmbedBm25Encoder(language="spanish")
    builder = QdrantIndexBuilder(
        client=client,
        embedding_provider=FixtureEmbeddingProvider(),
        sparse_encoder=encoder,
        active_alias=ACTIVE_ALIAS,
        batch_size=2,
    )
    collection = await builder.build_index(CORPUS, _signature())
    retriever = QdrantRetriever(
        client=client,
        embedding_provider=FixtureEmbeddingProvider(),
        sparse_encoder=encoder,
        collection=ACTIVE_ALIAS,
        expected_signature=_signature(),
    )
    return client, collection, retriever


def test_bm25_finds_identifier_acronym_and_preserves_spanish_negation(tmp_path: Path) -> None:
    """Dropping identifiers, acronyms or negation would rank the wrong technical record."""
    from application.ports.outbound.retriever import RetrievalRequest

    async def scenario() -> None:
        client, _, retriever = await _build_retriever(tmp_path)
        try:
            literal = await retriever.retrieve(RetrievalRequest("ZXQ-991", 2, "bm25"))
            acronym = await retriever.retrieve(RetrievalRequest("ATX", 2, "bm25"))
            negated = await retriever.retrieve(RetrievalRequest("no autorizado", 2, "bm25"))
            assert literal[0].chunk_id == "chunk-literal"
            assert acronym[0].chunk_id == "chunk-literal"
            assert negated[0].chunk_id == "chunk-literal"
        finally:
            await client.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("negation", ["no", "sin", "nunca", "ni"])
def test_spanish_bm25_keeps_negation_as_contrastive_evidence(negation: str) -> None:
    """Putting a negation token back into stopwords would collapse opposite documents."""
    from infrastructure.adapters.outbound.retriever.qdrant_retriever import (
        FastEmbedBm25Encoder,
    )

    async def scenario() -> None:
        encoder = FastEmbedBm25Encoder(language="spanish")
        query = await encoder.embed_query(negation)
        affirmative, negative = await encoder.embed_documents(
            ("registro autorizado", f"registro {negation} autorizado")
        )
        query_ids = set(query.indices)
        assert query_ids
        assert query_ids.isdisjoint(affirmative.indices)
        assert query_ids <= set(negative.indices)

    asyncio.run(scenario())


def test_dense_retrieval_finds_concept_without_literal_overlap(tmp_path: Path) -> None:
    """Using lexical lookup in dense mode would miss the paraphrased weather concept."""
    from application.ports.outbound.retriever import RetrievalRequest

    async def scenario() -> None:
        client, _, retriever = await _build_retriever(tmp_path)
        try:
            chunks = await retriever.retrieve(
                RetrievalRequest("protección meteorológica", 1, "dense")
            )
            assert chunks == (CORPUS[1],)
        finally:
            await client.close()

    asyncio.run(scenario())


def test_native_hybrid_rrf_returns_only_known_unique_chunk_ids(tmp_path: Path) -> None:
    """A broken fusion or payload mapper could duplicate or invent chunk identities."""
    from application.ports.outbound.retriever import RetrievalRequest

    async def scenario() -> None:
        client, _, retriever = await _build_retriever(tmp_path)
        try:
            chunks = await retriever.retrieve(
                RetrievalRequest("ZXQ-991 protección meteorológica", 3, "hybrid")
            )
            ids = tuple(chunk.chunk_id for chunk in chunks)
            assert ids
            assert len(ids) == len(set(ids))
            assert set(ids) <= {chunk.chunk_id for chunk in CORPUS}
        finally:
            await client.close()

    asyncio.run(scenario())


def test_retrieval_rejects_incompatible_active_index_signature(tmp_path: Path) -> None:
    """A retriever must not silently query vectors built with another dimension or model."""
    from application.models.retrieval import IncompatibleIndexError
    from infrastructure.adapters.outbound.retriever.qdrant_retriever import QdrantRetriever

    async def scenario() -> None:
        client, _, retriever = await _build_retriever(tmp_path)
        incompatible = replace(_signature(), embedding_model="fixture-embedding-2")
        mismatched = QdrantRetriever(
            client=client,
            embedding_provider=retriever.embedding_provider,
            sparse_encoder=retriever.sparse_encoder,
            collection=ACTIVE_ALIAS,
            expected_signature=incompatible,
        )
        try:
            from application.ports.outbound.retriever import RetrievalRequest

            with pytest.raises(IncompatibleIndexError, match="embedding_model"):
                await mismatched.retrieve(RetrievalRequest("granizo", 1, "dense"))
        finally:
            await client.close()

    asyncio.run(scenario())


def test_failed_candidate_validation_does_not_change_active_alias(tmp_path: Path) -> None:
    """Publishing before validating the candidate would replace a usable index on failure."""
    from infrastructure.adapters.outbound.retriever.index_builder import (
        IndexPublicationError,
        QdrantIndexBuilder,
    )
    from infrastructure.adapters.outbound.retriever.qdrant_retriever import FastEmbedBm25Encoder

    class RejectingValidationBuilder(QdrantIndexBuilder):
        async def _validate_candidate(
            self, collection: str, signature: IndexSignature, expected_count: int
        ) -> None:
            await super()._validate_candidate(collection, signature, expected_count)
            raise IndexPublicationError("injected failure after count and signature validation")

    async def scenario() -> None:
        client, original, _ = await _build_retriever(tmp_path)
        collections_before = {item.name for item in (await client.get_collections()).collections}
        builder = RejectingValidationBuilder(
            client=client,
            embedding_provider=FixtureEmbeddingProvider(),
            sparse_encoder=FastEmbedBm25Encoder(language="spanish"),
            active_alias=ACTIVE_ALIAS,
        )
        try:
            with pytest.raises(IndexPublicationError, match="after count and signature"):
                await builder.build_index(CORPUS, _signature())
            aliases = await client.get_aliases()
            active = next(alias for alias in aliases.aliases if alias.alias_name == ACTIVE_ALIAS)
            assert active.collection_name == original
            assert {
                item.name for item in (await client.get_collections()).collections
            } == collections_before
        finally:
            await client.close()

    asyncio.run(scenario())


def test_applied_alias_update_followed_by_connection_error_keeps_active_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deleting an ambiguously published candidate would leave the active alias dangling."""
    from infrastructure.adapters.outbound.retriever.index_builder import QdrantIndexBuilder
    from infrastructure.adapters.outbound.retriever.qdrant_retriever import FastEmbedBm25Encoder

    async def scenario() -> None:
        client, original, _ = await _build_retriever(tmp_path)
        update_aliases = client.update_collection_aliases

        async def apply_then_disconnect(
            change_aliases_operations: Sequence[
                models.CreateAliasOperation
                | models.RenameAliasOperation
                | models.DeleteAliasOperation
            ],
            timeout: int | None = None,
            **kwargs: object,
        ) -> bool:
            await update_aliases(
                change_aliases_operations=change_aliases_operations,
                timeout=timeout,
                **kwargs,
            )
            raise ResponseHandlingException(
                ConnectionError("connection lost after Qdrant applied alias update")
            )

        monkeypatch.setattr(client, "update_collection_aliases", apply_then_disconnect)
        builder = QdrantIndexBuilder(
            client=client,
            embedding_provider=FixtureEmbeddingProvider(),
            sparse_encoder=FastEmbedBm25Encoder(language="spanish"),
            active_alias=ACTIVE_ALIAS,
        )
        try:
            published = await builder.build_index(CORPUS, _signature())
            aliases = await client.get_aliases()
            active = next(alias for alias in aliases.aliases if alias.alias_name == ACTIVE_ALIAS)
            assert active.collection_name == published
            assert active.collection_name != original
            assert (await client.get_collection(ACTIVE_ALIAS)).points_count == len(CORPUS)
        finally:
            await client.close()

    asyncio.run(scenario())


def test_unverifiable_alias_update_preserves_candidate_and_previous_active_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unknown publication state must preserve both possible active collections."""
    from infrastructure.adapters.outbound.retriever.index_builder import (
        AmbiguousIndexPublicationError,
        QdrantIndexBuilder,
    )
    from infrastructure.adapters.outbound.retriever.qdrant_retriever import FastEmbedBm25Encoder

    async def scenario() -> None:
        client, original, _ = await _build_retriever(tmp_path)
        get_aliases = client.get_aliases
        collections_before = {item.name for item in (await client.get_collections()).collections}
        alias_reads = 0

        async def disconnect_before_confirmation(
            change_aliases_operations: Sequence[
                models.CreateAliasOperation
                | models.RenameAliasOperation
                | models.DeleteAliasOperation
            ],
            timeout: int | None = None,
            **kwargs: object,
        ) -> bool:
            del change_aliases_operations, timeout, kwargs
            raise ConnectionError("alias update outcome is unknown")

        async def first_read_then_disconnect(**kwargs: object) -> models.CollectionsAliasesResponse:
            nonlocal alias_reads
            alias_reads += 1
            if alias_reads > 1:
                raise ConnectionError("alias reconciliation is unavailable")
            return await get_aliases(**kwargs)

        monkeypatch.setattr(client, "update_collection_aliases", disconnect_before_confirmation)
        monkeypatch.setattr(client, "get_aliases", first_read_then_disconnect)
        builder = QdrantIndexBuilder(
            client=client,
            embedding_provider=FixtureEmbeddingProvider(),
            sparse_encoder=FastEmbedBm25Encoder(language="spanish"),
            active_alias=ACTIVE_ALIAS,
        )
        try:
            with pytest.raises(AmbiguousIndexPublicationError, match="could not verify"):
                await builder.build_index(CORPUS, _signature())
            collections_after = {item.name for item in (await client.get_collections()).collections}
            assert collections_before < collections_after
            assert len(collections_after - collections_before) == 1
            active = next(
                alias for alias in (await get_aliases()).aliases if alias.alias_name == ACTIVE_ALIAS
            )
            assert active.collection_name == original
            assert (await client.get_collection(ACTIVE_ALIAS)).points_count == len(CORPUS)
        finally:
            await client.close()

    asyncio.run(scenario())


def test_builder_rejects_chunk_without_evidence_identifiers(tmp_path: Path) -> None:
    """Publishing a source-free chunk would make later citations unverifiable."""
    from infrastructure.adapters.outbound.retriever.index_builder import (
        IndexPublicationError,
        QdrantIndexBuilder,
    )
    from infrastructure.adapters.outbound.retriever.qdrant_retriever import FastEmbedBm25Encoder

    async def scenario() -> None:
        client = AsyncQdrantClient(path=str(tmp_path / "qdrant"))
        builder = QdrantIndexBuilder(
            client=client,
            embedding_provider=FixtureEmbeddingProvider(),
            sparse_encoder=FastEmbedBm25Encoder(language="spanish"),
            active_alias=ACTIVE_ALIAS,
        )
        source_free = replace(CORPUS[0], evidence_ids=())
        try:
            with pytest.raises(IndexPublicationError, match="evidence_ids"):
                await builder.build_index((source_free,), _signature())
            assert (await client.get_collections()).collections == []
        finally:
            await client.close()

    asyncio.run(scenario())


def test_retriever_rejects_payload_without_evidence_identifiers(tmp_path: Path) -> None:
    """An empty evidence payload must fail instead of producing an uncitable chunk."""
    from application.ports.outbound.retriever import RetrievalRequest
    from infrastructure.adapters.outbound.retriever.qdrant_retriever import InvalidIndexDataError

    async def scenario() -> None:
        client, collection, retriever = await _build_retriever(tmp_path)
        weather_point = str(uuid.uuid5(uuid.NAMESPACE_URL, "chunk-weather"))
        await client.set_payload(
            collection_name=collection,
            payload={"evidence_ids": []},
            points=[weather_point],
            wait=True,
        )
        try:
            with pytest.raises(InvalidIndexDataError, match="chunk payload"):
                await retriever.retrieve(RetrievalRequest("protección meteorológica", 1, "dense"))
        finally:
            await client.close()

    asyncio.run(scenario())


def test_collection_is_validated_before_atomic_alias_publication(tmp_path: Path) -> None:
    """An incomplete batch or missing signature metadata must not become the active index."""

    async def scenario() -> None:
        client, collection, _ = await _build_retriever(tmp_path)
        try:
            info = await client.get_collection(collection)
            aliases = await client.get_aliases()
            active = next(alias for alias in aliases.aliases if alias.alias_name == ACTIVE_ALIAS)
            assert info.points_count == len(CORPUS)
            assert info.config.metadata == {
                "index_signature": {
                    "chunker": "fixture-chunker-1",
                    "dimensions": 3,
                    "document_hash": DOCUMENT_HASH,
                    "embedding_model": "fixture-embedding-1",
                    "lexical_language": "spanish",
                    "parser": "fixture-parser-1",
                }
            }
            assert active.collection_name == collection
            assert re.fullmatch(r"allianz-[0-9a-f]{12}-[0-9a-f]{12}", collection)
        finally:
            await client.close()

    asyncio.run(scenario())


def test_collection_uses_named_dense_and_bm25_vectors(tmp_path: Path) -> None:
    """Using unnamed or non-IDF sparse vectors would violate query routing and BM25 scoring."""

    async def scenario() -> None:
        client, collection, _ = await _build_retriever(tmp_path)
        try:
            info = await client.get_collection(collection)
            vectors = info.config.params.vectors
            sparse = info.config.params.sparse_vectors
            assert isinstance(vectors, dict)
            assert set(vectors) == {"dense"}
            assert vectors["dense"].size == 3
            assert sparse is not None
            assert set(sparse) == {"bm25"}
            assert sparse["bm25"].modifier == models.Modifier.IDF
        finally:
            await client.close()

    asyncio.run(scenario())
