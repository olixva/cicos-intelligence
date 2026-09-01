"""Validated, cached OpenAI dense embeddings behind the application port."""

import asyncio
import logging
import math
import os
from collections.abc import Awaitable, Callable, Sequence
from typing import Protocol

from openai import AsyncOpenAI, RateLimitError
from openai.types import CreateEmbeddingResponse

logger = logging.getLogger(__name__)

type Sleep = Callable[[float], Awaitable[None]]


class MissingEmbeddingCredentialsError(RuntimeError):
    """Raised before transport construction when no provider credential is configured."""


class InvalidEmbeddingResponseError(RuntimeError):
    """Raised when a provider response violates order, count, or dimension contracts."""


class EmbeddingTransport(Protocol):
    """Small typed seam around the generated OpenAI client."""

    def create(
        self, *, texts: Sequence[str], model: str, dimensions: int
    ) -> Awaitable[CreateEmbeddingResponse]: ...


class _OpenAITransport:
    def __init__(self, api_key: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key, max_retries=0)

    async def create(
        self, *, texts: Sequence[str], model: str, dimensions: int
    ) -> CreateEmbeddingResponse:
        return await self._client.embeddings.create(
            input=list(texts),
            model=model,
            dimensions=dimensions,
            encoding_format="float",
        )


class OpenAIEmbeddingProvider:
    """OpenAI embeddings with validated ordering, bounded retries, and a content cache."""

    def __init__(
        self,
        *,
        model: str,
        dimensions: int,
        api_key: str | None = None,
        transport: EmbeddingTransport | None = None,
        max_retries: int = 2,
        retry_delay_seconds: float = 0.25,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        if not model.strip():
            raise ValueError("embedding model must be nonempty")
        if type(dimensions) is not int or dimensions <= 0:
            raise ValueError("embedding dimensions must be a positive integer")
        if type(max_retries) is not int or max_retries < 0:
            raise ValueError("max_retries must be a nonnegative integer")
        if retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds must be nonnegative")
        self.model = model
        self.dimensions = dimensions
        self._api_key = api_key
        self._transport = transport
        self._max_retries = max_retries
        self._retry_delay_seconds = retry_delay_seconds
        self._sleep = sleep
        self._cache: dict[tuple[str, str], tuple[float, ...]] = {}

    async def embed(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        requested = tuple(texts)
        if not requested:
            return ()

        missing = tuple(
            dict.fromkeys(text for text in requested if (self.model, text) not in self._cache)
        )
        if missing:
            transport = self._get_transport()
            vectors = await self._request_with_retries(transport, missing)
            validated = self._validate_response(vectors, expected_count=len(missing))
            self._cache.update(
                ((self.model, text), vector)
                for text, vector in zip(missing, validated, strict=True)
            )
        return tuple(self._cache[(self.model, text)] for text in requested)

    def _get_transport(self) -> EmbeddingTransport:
        if self._transport is not None:
            return self._transport
        api_key = self._api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise MissingEmbeddingCredentialsError("OPENAI_API_KEY is not configured")
        self._transport = _OpenAITransport(api_key)
        return self._transport

    async def _request_with_retries(
        self, transport: EmbeddingTransport, texts: tuple[str, ...]
    ) -> CreateEmbeddingResponse:
        for attempt in range(self._max_retries + 1):
            logger.info(
                "OpenAI embedding call model=%s texts=%d attempt=%d",
                self.model,
                len(texts),
                attempt + 1,
            )
            try:
                return await transport.create(
                    texts=texts,
                    model=self.model,
                    dimensions=self.dimensions,
                )
            except RateLimitError:
                if attempt >= self._max_retries:
                    raise
                delay = self._retry_delay_seconds * (2**attempt)
                logger.warning(
                    "OpenAI embedding rate limit; retrying model=%s attempt=%d delay_seconds=%s",
                    self.model,
                    attempt + 2,
                    delay,
                )
                await self._sleep(delay)
        raise RuntimeError("unreachable embedding retry state")

    def _validate_response(
        self, response: CreateEmbeddingResponse, *, expected_count: int
    ) -> tuple[tuple[float, ...], ...]:
        if len(response.data) != expected_count:
            raise InvalidEmbeddingResponseError("embedding response count does not match request")
        by_index: dict[int, tuple[float, ...]] = {}
        for item in response.data:
            if item.index in by_index or not 0 <= item.index < expected_count:
                raise InvalidEmbeddingResponseError("embedding response indexes are invalid")
            vector = tuple(float(value) for value in item.embedding)
            if len(vector) != self.dimensions:
                raise InvalidEmbeddingResponseError(
                    "embedding response dimension does not match index"
                )
            if not all(math.isfinite(value) for value in vector):
                raise InvalidEmbeddingResponseError("embedding response contains non-finite values")
            by_index[item.index] = vector
        if set(by_index) != set(range(expected_count)):
            raise InvalidEmbeddingResponseError("embedding response indexes are incomplete")
        return tuple(by_index[index] for index in range(expected_count))
