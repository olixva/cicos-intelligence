"""OpenAI embedding boundary tests with typed, fully local transports."""

import asyncio
from collections.abc import Sequence

import httpx
import pytest
from openai import RateLimitError
from openai.types import CreateEmbeddingResponse
from openai.types.create_embedding_response import Usage
from openai.types.embedding import Embedding


def _response(
    vectors: Sequence[Sequence[float]], indexes: Sequence[int]
) -> CreateEmbeddingResponse:
    return CreateEmbeddingResponse(
        data=[
            Embedding(embedding=list(vector), index=index, object="embedding")
            for vector, index in zip(vectors, indexes, strict=True)
        ],
        model="fixture-model",
        object="list",
        usage=Usage(prompt_tokens=1, total_tokens=1),
    )


class ScriptedTransport:
    def __init__(self, outcomes: Sequence[CreateEmbeddingResponse | Exception]) -> None:
        self._outcomes = list(outcomes)
        self.inputs: list[tuple[str, ...]] = []

    async def create(
        self, *, texts: Sequence[str], model: str, dimensions: int
    ) -> CreateEmbeddingResponse:
        del model, dimensions
        self.inputs.append(tuple(texts))
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def test_embeddings_preserve_input_order_and_cache_by_model_and_text() -> None:
    """Trusting response order or omitting cache identity would reorder or repeat paid work."""
    from infrastructure.adapters.outbound.embedding_provider.openai_embedding_provider import (
        OpenAIEmbeddingProvider,
    )

    async def scenario() -> None:
        transport = ScriptedTransport([_response(((0.0, 1.0), (1.0, 0.0)), (1, 0))])
        provider = OpenAIEmbeddingProvider(model="fixture-model", dimensions=2, transport=transport)
        first = await provider.embed(("alpha", "beta"))
        second = await provider.embed(("beta", "alpha"))
        assert first == ((1.0, 0.0), (0.0, 1.0))
        assert second == ((0.0, 1.0), (1.0, 0.0))
        assert transport.inputs == [("alpha", "beta")]

    asyncio.run(scenario())


def test_missing_key_fails_before_constructing_or_calling_openai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing credential must never fall through to a provider request."""
    from infrastructure.adapters.outbound.embedding_provider.openai_embedding_provider import (
        MissingEmbeddingCredentialsError,
        OpenAIEmbeddingProvider,
    )

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    async def scenario() -> None:
        provider = OpenAIEmbeddingProvider(model="fixture-model", dimensions=2, api_key=None)
        with pytest.raises(MissingEmbeddingCredentialsError):
            await provider.embed(("alpha",))

    asyncio.run(scenario())


def test_invalid_transport_response_is_rejected_and_not_cached() -> None:
    """Wrong vector dimensions must fail rather than poisoning the content cache."""
    from infrastructure.adapters.outbound.embedding_provider.openai_embedding_provider import (
        InvalidEmbeddingResponseError,
        OpenAIEmbeddingProvider,
    )

    async def scenario() -> None:
        transport = ScriptedTransport(
            [_response(((1.0, 0.0, 0.0),), (0,)), _response(((1.0, 0.0),), (0,))]
        )
        provider = OpenAIEmbeddingProvider(model="fixture-model", dimensions=2, transport=transport)
        with pytest.raises(InvalidEmbeddingResponseError, match="dimension"):
            await provider.embed(("alpha",))
        assert await provider.embed(("alpha",)) == ((1.0, 0.0),)
        assert transport.inputs == [("alpha",), ("alpha",)]

    asyncio.run(scenario())


def test_rate_limit_is_retried_with_a_bounded_attempt_count() -> None:
    """Failing to retry a transient 429, or retrying forever, would break ingestion safety."""
    from infrastructure.adapters.outbound.embedding_provider.openai_embedding_provider import (
        OpenAIEmbeddingProvider,
    )

    async def no_wait(_: float) -> None:
        return None

    async def scenario() -> None:
        request = httpx.Request("POST", "https://api.openai.test/v1/embeddings")
        response = httpx.Response(429, request=request)
        rate_limit = RateLimitError("rate limited", response=response, body=None)
        transport = ScriptedTransport([rate_limit, _response(((1.0, 0.0),), (0,))])
        provider = OpenAIEmbeddingProvider(
            model="fixture-model",
            dimensions=2,
            transport=transport,
            max_retries=1,
            sleep=no_wait,
        )
        assert await provider.embed(("alpha",)) == ((1.0, 0.0),)
        assert transport.inputs == [("alpha",), ("alpha",)]

    asyncio.run(scenario())
