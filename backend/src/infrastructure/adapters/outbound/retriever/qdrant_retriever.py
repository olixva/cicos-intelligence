"""Qdrant dense, Spanish BM25, and native hybrid retrieval."""

import asyncio
from collections.abc import Awaitable, Sequence
from typing import Any, Protocol, cast

from fastembed.sparse.bm25 import Bm25
from qdrant_client import AsyncQdrantClient, models

from application.models.retrieval import (
    Chunk,
    FusionStrategy,
    GeneratorKind,
    IndexSignature,
    RerankerKind,
    RetrievalMode,
    RulesetKind,
    VisionKind,
    assert_compatible,
)
from application.ports.outbound.embedding_provider import EmbeddingProvider
from application.ports.outbound.retriever import RetrievalRequest

_NEGATION_TOKENS = frozenset({"jamás", "ni", "ningún", "ninguna", "ninguno", "no", "nunca", "sin"})


class InvalidIndexDataError(RuntimeError):
    """Raised when Qdrant metadata or chunk payloads violate the index contract."""


class SparseEncoder(Protocol):
    """Local sparse encoder; documents and queries use different BM25 weights."""

    def embed_documents(
        self, texts: Sequence[str]
    ) -> Awaitable[tuple[models.SparseVector, ...]]: ...

    def embed_query(self, text: str) -> Awaitable[models.SparseVector]: ...


class FastEmbedBm25Encoder:
    """FastEmbed BM25 with Spanish stemming and negation-bearing stopwords retained."""

    def __init__(self, *, language: str) -> None:
        if language != "spanish":
            raise ValueError("BM25 lexical language must be spanish")
        self.language = language
        self._model = Bm25("Qdrant/bm25", language=language)
        self._model.stopwords.difference_update(_NEGATION_TOKENS)

    async def embed_documents(self, texts: Sequence[str]) -> tuple[models.SparseVector, ...]:
        return await asyncio.to_thread(self._embed_documents_sync, tuple(texts))

    async def embed_query(self, text: str) -> models.SparseVector:
        return await asyncio.to_thread(self._embed_query_sync, text)

    def _embed_documents_sync(self, texts: tuple[str, ...]) -> tuple[models.SparseVector, ...]:
        return tuple(_to_sparse_vector(item) for item in self._model.embed(texts))

    def _embed_query_sync(self, text: str) -> models.SparseVector:
        return _to_sparse_vector(next(iter(self._model.query_embed(text))))


class QdrantRetriever:
    """Read one signature-compatible Qdrant collection through interchangeable modes."""

    def __init__(
        self,
        *,
        client: AsyncQdrantClient,
        embedding_provider: EmbeddingProvider,
        sparse_encoder: SparseEncoder,
        collection: str,
        expected_signature: IndexSignature,
    ) -> None:
        if not collection.strip():
            raise ValueError("collection must be nonempty")
        self.client = client
        self.embedding_provider = embedding_provider
        self.sparse_encoder = sparse_encoder
        self.collection = collection
        self.expected_signature = expected_signature

    async def retrieve(self, request: RetrievalRequest) -> tuple[Chunk, ...]:
        await self._assert_active_signature()
        if request.mode == "dense":
            dense = await self._dense_query(request.text)
            response = await self.client.query_points(
                collection_name=self.collection,
                query=list(dense),
                using="dense",
                limit=request.limit,
                with_payload=True,
            )
        elif request.mode == "bm25":
            sparse = await self.sparse_encoder.embed_query(request.text)
            response = await self.client.query_points(
                collection_name=self.collection,
                query=sparse,
                using="bm25",
                limit=request.limit,
                with_payload=True,
            )
        else:
            dense, sparse = await asyncio.gather(
                self._dense_query(request.text), self.sparse_encoder.embed_query(request.text)
            )
            response = await self.client.query_points(
                collection_name=self.collection,
                prefetch=[
                    models.Prefetch(query=list(dense), using="dense", limit=request.limit),
                    models.Prefetch(query=sparse, using="bm25", limit=request.limit),
                ],
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=request.limit,
                with_payload=True,
            )
        return _chunks_from_points(response.points)

    async def _dense_query(self, text: str) -> tuple[float, ...]:
        result = await self.embedding_provider.embed((text,))
        if len(result) != 1 or len(result[0]) != self.expected_signature.dimensions:
            raise InvalidIndexDataError("dense query dimension does not match index signature")
        return result[0]

    async def _assert_active_signature(self) -> None:
        info = await self.client.get_collection(self.collection)
        actual = signature_from_metadata(info.config.metadata)
        assert_compatible(actual, self.expected_signature)


def signature_metadata(signature: IndexSignature) -> dict[str, dict[str, object]]:
    """Serialize the full compatibility boundary into Qdrant collection metadata."""
    return {
        "index_signature": {
            "chunker": signature.chunker,
            "dimensions": signature.dimensions,
            "document_hash": signature.document_hash,
            "embedding_model": signature.embedding_model,
            "lexical_language": signature.lexical_language,
            "parser": signature.parser,
            "retrieval_mode": signature.retrieval_mode,
            "fusion": signature.fusion,
            "reranker": signature.reranker,
            "vision": signature.vision,
            "ruleset": signature.ruleset,
            "generator": signature.generator,
            "prompt_versions": dict(signature.prompt_versions or {}),
        }
    }


def signature_from_metadata(metadata: dict[str, Any] | None) -> IndexSignature:
    """Read a complete signature, rejecting partial or incorrectly typed metadata.

    Collections written before the extended signature (T3) only
    carry the six base fields; for those we recover the legacy
    defaults so a freshly built ``IndexSignature`` still compares
    equal to the historical collection metadata via
    ``assert_compatible``.
    """
    if not isinstance(metadata, dict):
        raise InvalidIndexDataError("collection has no index signature metadata")
    raw_value = metadata.get("index_signature")
    if not isinstance(raw_value, dict):
        raise InvalidIndexDataError("collection has no index signature metadata")
    raw = cast(dict[str, object], raw_value)
    try:
        document_hash = raw["document_hash"]
        parser = raw["parser"]
        chunker = raw["chunker"]
        embedding_model = raw["embedding_model"]
        dimensions = raw["dimensions"]
        lexical_language = raw["lexical_language"]
    except KeyError as error:
        raise InvalidIndexDataError("collection index signature metadata is incomplete") from error
    if (
        not all(
            isinstance(value, str)
            for value in (document_hash, parser, chunker, embedding_model, lexical_language)
        )
        or type(dimensions) is not int
    ):
        raise InvalidIndexDataError("collection index signature metadata has invalid types")

    def _string_or_default(key: str, default: str) -> str:
        value = raw.get(key, default)
        if not isinstance(value, str):
            raise InvalidIndexDataError(f"collection index signature field {key} is invalid")
        return value

    retrieval_mode = _string_or_default("retrieval_mode", "hybrid")
    fusion = _string_or_default("fusion", "rrf")
    reranker = _string_or_default("reranker", "none")
    vision = _string_or_default("vision", "none")
    ruleset = _string_or_default("ruleset", "audit-required")
    generator = _string_or_default("generator", "openai-responses")
    if "prompt_versions" in raw:
        prompt_versions_raw = raw["prompt_versions"]
        if not isinstance(prompt_versions_raw, dict):
            raise InvalidIndexDataError("collection index signature prompt_versions is invalid")
        prompt_versions: dict[str, str] | None = dict(cast(dict[str, str], prompt_versions_raw))
    else:
        prompt_versions = None
    return IndexSignature(
        cast(str, document_hash),
        cast(str, parser),
        cast(str, chunker),
        cast(str, embedding_model),
        dimensions,
        cast(str, lexical_language),
        retrieval_mode=cast(RetrievalMode, retrieval_mode),
        fusion=cast(FusionStrategy, fusion),
        reranker=cast(RerankerKind, reranker),
        vision=cast(VisionKind, vision),
        ruleset=cast(RulesetKind, ruleset),
        generator=cast(GeneratorKind, generator),
        prompt_versions=prompt_versions,
    )


def _to_sparse_vector(item: Any) -> models.SparseVector:
    indices = tuple(int(value) for value in item.indices.tolist())
    values = tuple(float(value) for value in item.values.tolist())
    return models.SparseVector(indices=list(indices), values=list(values))


def _chunks_from_points(points: Sequence[models.ScoredPoint]) -> tuple[Chunk, ...]:
    chunks: list[Chunk] = []
    seen: set[str] = set()
    for point in points:
        payload_value = point.payload
        if not isinstance(payload_value, dict):
            raise InvalidIndexDataError("retrieval point has no chunk payload")
        payload = cast(dict[str, object], payload_value)
        chunk_id = payload.get("chunk_id")
        text = payload.get("text")
        evidence_ids = payload.get("evidence_ids")
        if (
            not isinstance(chunk_id, str)
            or not chunk_id
            or not isinstance(text, str)
            or not isinstance(evidence_ids, list)
        ):
            raise InvalidIndexDataError("retrieval point has an invalid chunk payload")
        evidence_items = cast(list[object], evidence_ids)
        if not evidence_items or not all(
            isinstance(item, str) and item.strip() for item in evidence_items
        ):
            raise InvalidIndexDataError("retrieval point has an invalid chunk payload")
        if chunk_id in seen:
            continue
        seen.add(chunk_id)
        chunks.append(Chunk(chunk_id, text, tuple(cast(str, item) for item in evidence_items)))
    return tuple(chunks)
