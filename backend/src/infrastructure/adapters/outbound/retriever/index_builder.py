"""Atomic publication of validated Qdrant retrieval indexes."""

import hashlib
import json
import logging
import uuid
from collections.abc import Sequence

from qdrant_client import AsyncQdrantClient, models

from application.models.retrieval import Chunk, IndexSignature, assert_compatible
from application.ports.outbound.embedding_provider import EmbeddingProvider
from infrastructure.adapters.outbound.retriever.qdrant_retriever import (
    SparseEncoder,
    signature_from_metadata,
    signature_metadata,
)

logger = logging.getLogger(__name__)


class IndexPublicationError(RuntimeError):
    """Raised when a candidate collection cannot be validated and published."""


class QdrantIndexBuilder:
    """Build a new collection completely, validate it, then atomically switch its alias."""

    def __init__(
        self,
        *,
        client: AsyncQdrantClient,
        embedding_provider: EmbeddingProvider,
        sparse_encoder: SparseEncoder,
        active_alias: str,
        batch_size: int = 64,
    ) -> None:
        if not active_alias.strip():
            raise ValueError("active_alias must be nonempty")
        if type(batch_size) is not int or batch_size <= 0:
            raise ValueError("batch_size must be a positive integer")
        self.client = client
        self.embedding_provider = embedding_provider
        self.sparse_encoder = sparse_encoder
        self.active_alias = active_alias
        self.batch_size = batch_size

    async def build_index(self, chunks: Sequence[Chunk], signature: IndexSignature) -> str:
        ordered = tuple(chunks)
        if not ordered:
            raise IndexPublicationError("cannot publish an empty index")
        if len({chunk.chunk_id for chunk in ordered}) != len(ordered):
            raise IndexPublicationError("chunk IDs must be unique")

        dense = await self.embedding_provider.embed(tuple(chunk.text for chunk in ordered))
        if len(dense) != len(ordered):
            raise IndexPublicationError("dense embedding count does not match chunks")
        if any(len(vector) != signature.dimensions for vector in dense):
            raise IndexPublicationError("dense embedding dimension does not match index signature")
        sparse = await self.sparse_encoder.embed_documents(tuple(chunk.text for chunk in ordered))
        if len(sparse) != len(ordered):
            raise IndexPublicationError("sparse embedding count does not match chunks")

        collection = _candidate_collection_name(signature)
        created = False
        try:
            created = await self.client.create_collection(
                collection_name=collection,
                vectors_config={
                    "dense": models.VectorParams(
                        size=signature.dimensions,
                        distance=models.Distance.COSINE,
                    )
                },
                sparse_vectors_config={
                    "bm25": models.SparseVectorParams(modifier=models.Modifier.IDF)
                },
                metadata=signature_metadata(signature),
            )
            if not created:
                raise IndexPublicationError("Qdrant did not create the candidate collection")

            for start in range(0, len(ordered), self.batch_size):
                stop = min(start + self.batch_size, len(ordered))
                points = [
                    models.PointStruct(
                        id=str(uuid.uuid5(uuid.NAMESPACE_URL, chunk.chunk_id)),
                        vector={"dense": list(dense[index]), "bm25": sparse[index]},
                        payload={
                            "chunk_id": chunk.chunk_id,
                            "evidence_ids": list(chunk.evidence_ids),
                            "text": chunk.text,
                        },
                    )
                    for index, chunk in enumerate(ordered[start:stop], start=start)
                ]
                logger.info(
                    "Qdrant index upsert collection=%s start=%d count=%d",
                    collection,
                    start,
                    len(points),
                )
                await self.client.upsert(collection_name=collection, points=points, wait=True)

            await self._validate_candidate(collection, signature, len(ordered))
            await self._publish_alias(collection)
            return collection
        except Exception:
            if created:
                try:
                    await self.client.delete_collection(collection_name=collection)
                except Exception:
                    logger.exception(
                        "Could not remove failed Qdrant candidate collection=%s", collection
                    )
            raise

    async def _validate_candidate(
        self, collection: str, signature: IndexSignature, expected_count: int
    ) -> None:
        count = await self.client.count(collection_name=collection, exact=True)
        if count.count != expected_count:
            raise IndexPublicationError(
                f"candidate point count {count.count} does not match {expected_count}"
            )
        info = await self.client.get_collection(collection)
        assert_compatible(signature_from_metadata(info.config.metadata), signature)
        vectors = info.config.params.vectors
        sparse = info.config.params.sparse_vectors
        if (
            not isinstance(vectors, dict)
            or set(vectors) != {"dense"}
            or vectors["dense"].size != signature.dimensions
            or sparse is None
            or set(sparse) != {"bm25"}
            or sparse["bm25"].modifier != models.Modifier.IDF
        ):
            raise IndexPublicationError("candidate vector configuration is incompatible")

    async def _publish_alias(self, collection: str) -> None:
        aliases = await self.client.get_aliases()
        active = next(
            (alias for alias in aliases.aliases if alias.alias_name == self.active_alias), None
        )
        operations: list[models.DeleteAliasOperation | models.CreateAliasOperation] = []
        if active is not None:
            operations.append(
                models.DeleteAliasOperation(
                    delete_alias=models.DeleteAlias(alias_name=self.active_alias)
                )
            )
        operations.append(
            models.CreateAliasOperation(
                create_alias=models.CreateAlias(
                    collection_name=collection,
                    alias_name=self.active_alias,
                )
            )
        )
        published = await self.client.update_collection_aliases(
            change_aliases_operations=operations
        )
        if not published:
            raise IndexPublicationError("Qdrant did not publish the active alias")


def _candidate_collection_name(signature: IndexSignature) -> str:
    encoded = json.dumps(
        signature_metadata(signature), sort_keys=True, separators=(",", ":")
    ).encode()
    signature_hash = hashlib.sha256(encoded).hexdigest()[:12]
    return f"allianz-{signature_hash}-{uuid.uuid4().hex[:12]}"
