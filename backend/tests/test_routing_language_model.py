"""Dedicated routing classifier for the auto router.

The router cannot reuse the question-flow ``OpenAILanguageModel`` because
its ``text_format=AnswerSchema`` constrains the status literal to the
four ``AnswerStatus`` values and provides no path for the model to
emit ``claim`` or ``clarification_required``. These tests pin the
dedicated ``OpenAIRoutingLanguageModel`` schema, validation and error
shapes.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, cast

import pytest

from application.models.query import QueryInput
from application.ports.outbound.language_model import (
    LanguageModelError,
    MissingLanguageModelCredentialsError,
    ModelOutputError,
    ModelTimeoutError,
)
from domain.models.routing import RouteClassification
from infrastructure.adapters.outbound.language_model.openai_routing_language_model import (
    OpenAIRoutingLanguageModel,
    ParsedRoutingResponse,
    RouteDecisionSchema,
    RoutingPrompt,
    RoutingTransport,
)


def _prompt() -> RoutingPrompt:
    return RoutingPrompt(name="auto-router", version=1, content="Clasifica la consulta.")


def _query() -> QueryInput:
    return QueryInput(text="¿Qué dice el manual?", language="es")


@dataclass
class _FakeParsedResponse(ParsedRoutingResponse):
    parsed: RouteDecisionSchema | None
    response_status: str = "completed"

    @property
    def output_parsed(self) -> object | None:
        return self.parsed

    @property
    def status(self) -> str:
        return self.response_status


@dataclass
class _FakeTransport(RoutingTransport):
    """Records the last call and returns a configurable parsed response."""

    parsed: RouteDecisionSchema | None = None
    response_status: str = "completed"
    raise_exc: Exception | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def parse(
        self,
        *,
        model: str,
        input: Any,
        text_format: type[RouteDecisionSchema],
        store: bool,
        timeout: float,
    ) -> ParsedRoutingResponse:
        self.calls.append(
            {"model": model, "text_format": text_format, "store": store, "timeout": timeout}
        )
        if self.raise_exc is not None:
            raise self.raise_exc
        return _FakeParsedResponse(parsed=self.parsed, response_status=self.response_status)


def test_router_classifier_returns_question_decision() -> None:
    transport = _FakeTransport(
        parsed=RouteDecisionSchema(decision="question", rationale="answered"),
    )
    classifier = OpenAIRoutingLanguageModel(
        model="gpt-5.4", prompt=_prompt(), transport=cast(Any, transport)
    )

    classification = asyncio.run(classifier.classify(_query()))

    assert classification == RouteClassification(decision="question", rationale="answered")
    assert len(transport.calls) == 1
    assert transport.calls[0]["text_format"] is RouteDecisionSchema


def test_router_classifier_returns_claim_decision() -> None:
    transport = _FakeTransport(
        parsed=RouteDecisionSchema(decision="claim", rationale="narrative"),
    )
    classifier = OpenAIRoutingLanguageModel(
        model="gpt-5.4", prompt=_prompt(), transport=cast(Any, transport)
    )

    classification = asyncio.run(classifier.classify(_query()))

    assert classification == RouteClassification(decision="claim", rationale="narrative")


def test_router_classifier_returns_clarification_decision() -> None:
    transport = _FakeTransport(
        parsed=RouteDecisionSchema(decision="clarification_required", rationale="faltan datos"),
    )
    classifier = OpenAIRoutingLanguageModel(
        model="gpt-5.4", prompt=_prompt(), transport=cast(Any, transport)
    )

    classification = asyncio.run(classifier.classify(_query()))

    assert classification == RouteClassification(
        decision="clarification_required", rationale="faltan datos"
    )


def test_router_classifier_rejects_none_parsed() -> None:
    transport = _FakeTransport(parsed=None)
    classifier = OpenAIRoutingLanguageModel(
        model="gpt-5.4", prompt=_prompt(), transport=cast(Any, transport)
    )

    with pytest.raises(ModelOutputError, match="invalid decision"):
        asyncio.run(classifier.classify(_query()))


def test_router_classifier_rejects_incomplete_response_status() -> None:
    transport = _FakeTransport(
        parsed=RouteDecisionSchema(decision="question", rationale=None),
        response_status="incomplete",
    )
    classifier = OpenAIRoutingLanguageModel(
        model="gpt-5.4", prompt=_prompt(), transport=cast(Any, transport)
    )

    with pytest.raises(ModelOutputError, match="incomplete"):
        asyncio.run(classifier.classify(_query()))


def test_router_classifier_wraps_timeout_as_model_timeout_error() -> None:
    import openai

    transport = _FakeTransport(raise_exc=openai.APITimeoutError(request=None))  # type: ignore[arg-type]
    classifier = OpenAIRoutingLanguageModel(
        model="gpt-5.4", prompt=_prompt(), transport=cast(Any, transport)
    )

    with pytest.raises(ModelTimeoutError):
        asyncio.run(classifier.classify(_query()))


def test_router_classifier_wraps_api_error_as_language_model_error() -> None:
    import openai

    transport = _FakeTransport(
        raise_exc=openai.APIError(message="boom", request=None, body=None)  # type: ignore[arg-type]
    )
    classifier = OpenAIRoutingLanguageModel(
        model="gpt-5.4", prompt=_prompt(), transport=cast(Any, transport)
    )

    with pytest.raises(LanguageModelError):
        asyncio.run(classifier.classify(_query()))


def test_router_classifier_raises_when_openai_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    classifier = OpenAIRoutingLanguageModel(model="gpt-5.4", prompt=_prompt())

    with pytest.raises(MissingLanguageModelCredentialsError):
        asyncio.run(classifier.classify(_query()))


def test_router_classifier_rejects_empty_model_at_construction() -> None:
    with pytest.raises(ValueError, match="routing model must be nonempty"):
        OpenAIRoutingLanguageModel(model="", prompt=_prompt())


def test_router_classifier_rejects_nonpositive_timeout() -> None:
    with pytest.raises(ValueError, match="timeout must be positive"):
        OpenAIRoutingLanguageModel(model="gpt-5.4", prompt=_prompt(), timeout_seconds=0)


def test_routing_prompt_rejects_empty_content() -> None:
    with pytest.raises(ValueError, match="nonempty"):
        RoutingPrompt(name="auto-router", version=1, content="")


def test_routing_prompt_rejects_nonpositive_version() -> None:
    with pytest.raises(ValueError, match="positive integer"):
        RoutingPrompt(name="auto-router", version=0, content="hola")