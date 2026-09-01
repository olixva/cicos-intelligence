"""Outbound port for atomic retrieval-index publication."""

from typing import Protocol

from application.models.retrieval import Chunk, IndexSignature


class IndexPublisher(Protocol):
    """Publish fully built chunks and return the concrete active collection name."""

    async def build_index(self, chunks: tuple[Chunk, ...], signature: IndexSignature) -> str:
        """Publish a signature-compatible index without exposing a partial version."""
        ...
