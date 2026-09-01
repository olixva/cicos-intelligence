"""Outbound retrieval contract independent from the vector database."""

from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Literal, Protocol

from application.models.retrieval import Chunk

type RetrievalMode = Literal["dense", "bm25", "hybrid"]


@dataclass(frozen=True, slots=True)
class RetrievalRequest:
    """A bounded textual retrieval request."""

    text: str
    limit: int
    mode: RetrievalMode

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("retrieval text must be nonempty")
        if type(self.limit) is not int or self.limit <= 0:
            raise ValueError("retrieval limit must be a positive integer")
        if self.mode not in ("dense", "bm25", "hybrid"):
            raise ValueError("retrieval mode must be dense, bm25, or hybrid")


class Retriever(Protocol):
    """Retrieve source-linked chunks for a request."""

    def retrieve(self, request: RetrievalRequest) -> Awaitable[tuple[Chunk, ...]]:
        """Return ranked chunks without duplicate identities."""
        ...
