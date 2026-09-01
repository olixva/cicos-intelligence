"""Dedicated structured-output classifier for the closed-enum auto router.

The auto router cannot reuse the question-flow ``OpenAILanguageModel``
because its ``text_format=AnswerSchema`` constrains the status literal
to ``answered | partial | insufficient_evidence | out_of_scope`` and
provides no path for the model to emit ``claim`` or
``clarification_required``. This adapter wraps the same SDK with its own
``text_format=RouteDecisionSchema`` so the model can produce any of the
three closed-enum routes.
"""

from __future__ import annotations

import json
import os
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Protocol, cast

from openai import APIError, APITimeoutError, AsyncOpenAI
from openai.types.responses import ResponseInputParam
from pydantic import BaseModel, ConfigDict, ValidationError

from application.models.query import QueryInput
from application.ports.outbound.language_model import (
    LanguageModelError,
    MissingLanguageModelCredentialsError,
    ModelOutputError,
    ModelTimeoutError,
)
from domain.models.routing import RouteClassification, RouteDecision


class _StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class RouteDecisionSchema(_StrictSchema):
    """Closed structured output emitted by the auto-router classifier."""

    decision: RouteDecision
    rationale: str | None = None


class ParsedRoutingResponse(Protocol):
    """View of the parsed Responses API result."""

    @property
    def output_parsed(self) -> object | None: ...

    @property
    def status(self) -> str: ...


class RoutingTransport(Protocol):
    """Typed seam over ``responses.parse`` for deterministic local tests."""

    def parse(
        self,
        *,
        model: str,
        input: ResponseInputParam,
        text_format: type[RouteDecisionSchema],
        store: bool,
        timeout: float,
    ) -> Awaitable[ParsedRoutingResponse]: ...


@dataclass(frozen=True, slots=True)
class RoutingPrompt:
    """Minimal prompt container for the router classifier."""

    name: str
    version: int
    content: str

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.content.strip():
            raise ValueError("routing prompt name and content must be nonempty")
        if type(self.version) is not int or self.version <= 0:
            raise ValueError("routing prompt version must be a positive integer")


class _OpenAIRoutingTransport:
    def __init__(self, api_key: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key, max_retries=0)

    async def parse(
        self,
        *,
        model: str,
        input: ResponseInputParam,
        text_format: type[RouteDecisionSchema],
        store: bool,
        timeout: float,
    ) -> ParsedRoutingResponse:
        response = await self._client.responses.parse(
            model=model,
            input=input,
            text_format=text_format,
            store=store,
            timeout=timeout,
        )
        return cast(ParsedRoutingResponse, response)


class OpenAIRoutingLanguageModel:
    """Generate one closed-enum routing decision per query."""

    def __init__(
        self,
        *,
        model: str,
        prompt: RoutingPrompt,
        api_key: str | None = None,
        transport: RoutingTransport | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        if not model.strip():
            raise ValueError("routing model must be nonempty")
        if timeout_seconds <= 0:
            raise ValueError("routing-model timeout must be positive")
        self.model = model
        self.prompt = prompt
        self._api_key = api_key
        self._transport = transport
        self._timeout_seconds = timeout_seconds

    async def classify(self, query: QueryInput) -> RouteClassification:
        messages = _routing_messages(self.prompt, query)
        try:
            response = await self._get_transport().parse(
                model=self.model,
                input=messages,
                text_format=RouteDecisionSchema,
                store=False,
                timeout=self._timeout_seconds,
            )
        except (APITimeoutError, TimeoutError) as error:
            raise ModelTimeoutError("routing model request timed out") from error
        except (ValidationError, ValueError) as error:
            raise ModelOutputError("routing model returned an invalid decision") from error
        except APIError as error:
            raise LanguageModelError("routing model provider request failed") from error

        if response.status == "incomplete":
            raise ModelOutputError("routing model returned an incomplete decision")
        parsed = response.output_parsed
        if parsed is None or not isinstance(parsed, RouteDecisionSchema):
            raise ModelOutputError("routing model returned an invalid decision")
        return RouteClassification(decision=parsed.decision, rationale=parsed.rationale)

    def _get_transport(self) -> RoutingTransport:
        if self._transport is not None:
            return self._transport
        api_key = self._api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise MissingLanguageModelCredentialsError("OPENAI_API_KEY is not configured")
        self._transport = _OpenAIRoutingTransport(api_key)
        return self._transport


def _routing_messages(
    prompt: RoutingPrompt, query: QueryInput
) -> ResponseInputParam:
    developer = (
        f"{prompt.content}\n\n"
        f"[prompt={prompt.name} version={prompt.version}]\n"
        "Emite exactamente una decisión del enum cerrado."
    )
    user_payload = json.dumps(
        {"text": query.text, "language": query.language}, ensure_ascii=False, sort_keys=True
    )
    return cast(
        ResponseInputParam,
        [
            {"role": "developer", "content": developer},
            {"role": "user", "content": user_payload},
        ],
    )