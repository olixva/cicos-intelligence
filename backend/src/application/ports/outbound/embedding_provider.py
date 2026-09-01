"""Outbound contract for dense text embeddings."""

from collections.abc import Awaitable, Sequence
from typing import Protocol


class EmbeddingProvider(Protocol):
    """Produce one dense vector per input text, in the same order."""

    def embed(self, texts: Sequence[str]) -> Awaitable[tuple[tuple[float, ...], ...]]:
        """Embed the supplied texts without changing their order."""
        ...
