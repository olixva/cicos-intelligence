"""OpenAI Responses structured-output boundary tests with no network calls."""

import asyncio
from dataclasses import dataclass
from typing import Literal

import pytest
from openai.types.responses import ResponseInputParam

from application.models.query import AnswerBlock, ContextEvidence, QueryInput, QuestionAnswer
from application.ports.outbound.language_model import ModelOutputError, ModelTimeoutError
from domain.models.evidence import PageEvidence
from infrastructure.adapters.outbound.language_model.openai_language_model import (
    AnswerSchema,
    ParsedResponseView,
)


def _context() -> tuple[ContextEvidence, ...]:
    page = PageEvidence(
        evidence_id="manual:page:7",
        document_hash="a" * 64,
        pdf_page=7,
        text="Texto completo privado para la generación.",
        printed_label="7",
        image_path="pages/7.png",
        regions=(),
    )
    return (ContextEvidence((page.evidence_id,), "Sólo este fragmento se entrega.", (page,)),)


@dataclass(slots=True)
class FakeParsedResponse:
    output_parsed: object | None
    status: Literal["completed", "incomplete"] = "completed"


class FakeResponsesTransport:
    def __init__(self, response: FakeParsedResponse | Exception) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    async def parse(
        self,
        *,
        model: str,
        input: ResponseInputParam,
        text_format: type[AnswerSchema],
        store: bool,
        timeout: float,
    ) -> ParsedResponseView:
        self.calls.append(
            {
                "model": model,
                "input": input,
                "text_format": text_format,
                "store": store,
                "timeout": timeout,
            }
        )
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_openai_responses_parse_is_structured_non_stored_and_receives_exact_context() -> None:
    """The provider boundary must parse a schema without storing or expanding context."""
    from infrastructure.adapters.outbound.language_model.openai_language_model import (
        AnswerBlockSchema,
        AnswerSchema,
        OpenAILanguageModel,
        PromptDefinition,
    )

    async def scenario() -> None:
        parsed = AnswerSchema(
            status="answered",
            blocks=(AnswerBlockSchema(text="Respuesta.", evidence_ids=("manual:page:7",)),),
        )
        transport = FakeResponsesTransport(FakeParsedResponse(parsed))
        model = OpenAILanguageModel(
            model="fixture-model",
            prompt=PromptDefinition("document-question", 4, "Responde con evidencia."),
            transport=transport,
        )

        answer = await model.generate(QueryInput("¿Qué dice?", "es"), _context())

        assert answer == QuestionAnswer(
            "answered", (AnswerBlock("Respuesta.", ("manual:page:7",)),)
        )
        call = transport.calls[0]
        assert call["model"] == "fixture-model"
        assert call["store"] is False
        assert call["text_format"] is AnswerSchema
        serialized_input = str(call["input"])
        assert "Sólo este fragmento se entrega." in serialized_input
        assert "Texto completo privado para la generación." not in serialized_input
        assert "manual:page:7" in serialized_input
        assert "prompt=document-question version=4" in serialized_input

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (FakeParsedResponse(None), "No parsed answer"),
        (FakeParsedResponse(None, status="incomplete"), "incomplete"),
        (ValueError("schema mismatch"), "invalid structured answer"),
    ],
)
def test_unusable_provider_output_raises_model_output_error(
    response: FakeParsedResponse | Exception, message: str
) -> None:
    """Refusal, truncation, or invalid schema must not become a fabricated answer."""
    from infrastructure.adapters.outbound.language_model.openai_language_model import (
        OpenAILanguageModel,
        PromptDefinition,
    )

    async def scenario() -> None:
        model = OpenAILanguageModel(
            model="fixture-model",
            prompt=PromptDefinition("document-question", 4, "Responde con evidencia."),
            transport=FakeResponsesTransport(response),
        )
        with pytest.raises(ModelOutputError, match=message):
            await model.generate(QueryInput("¿Qué dice?", "es"), _context())

    asyncio.run(scenario())


def test_provider_timeout_remains_a_technical_error() -> None:
    """A timeout cannot be reported as an evidence judgment."""
    from infrastructure.adapters.outbound.language_model.openai_language_model import (
        OpenAILanguageModel,
        PromptDefinition,
    )

    async def scenario() -> None:
        model = OpenAILanguageModel(
            model="fixture-model",
            prompt=PromptDefinition("document-question", 4, "Responde con evidencia."),
            transport=FakeResponsesTransport(TimeoutError("network timeout")),
        )
        with pytest.raises(ModelTimeoutError, match="timed out"):
            await model.generate(QueryInput("¿Qué dice?", "es"), _context())

    asyncio.run(scenario())


def test_answer_schema_to_application_dedupes_repeated_evidence_ids() -> None:
    """El proveedor a veces repite evidence_ids en un mismo bloque (p. ej. cuando
    cita el mismo fragmento varias veces en el JSON estructurado). El adaptador
    debe deduplicarlos preservando orden en lugar de propagar un ``ValueError``
    que tira la request con 500."""

    parsed = AnswerSchema(
        status="answered",
        blocks=(
            {
                "text": "Cita duplicada por el modelo.",
                "evidence_ids": (
                    "manual:page:7",
                    "manual:page:7",
                    "manual:page:9",
                ),
            },
        ),
    )

    application = parsed.to_application()

    assert application.status == "answered"
    assert application.blocks[0].evidence_ids == ("manual:page:7", "manual:page:9")
    assert len(application.blocks[0].evidence_ids) == len(set(application.blocks[0].evidence_ids))


def test_application_validation_failure_is_wrapped_as_model_output_error() -> None:
    """Schema-valid whitespace must not escape the provider boundary as a raw ValueError."""
    from infrastructure.adapters.outbound.language_model.openai_language_model import (
        AnswerBlockSchema,
        AnswerSchema,
        OpenAILanguageModel,
        PromptDefinition,
    )

    async def scenario() -> None:
        parsed = AnswerSchema(
            status="answered",
            blocks=(AnswerBlockSchema(text=" ", evidence_ids=("manual:page:7",)),),
        )
        model = OpenAILanguageModel(
            model="fixture-model",
            prompt=PromptDefinition("document-question", 4, "Responde con evidencia."),
            transport=FakeResponsesTransport(FakeParsedResponse(parsed)),
        )

        with pytest.raises(ModelOutputError, match="invalid structured answer"):
            await model.generate(QueryInput("¿Qué dice?", "es"), _context())

    asyncio.run(scenario())


def test_langfuse_prompt_lookup_requires_a_concrete_version() -> None:
    """Using a mutable prompt label would make experiment results irreproducible."""
    from infrastructure.adapters.outbound.language_model.openai_language_model import (
        load_langfuse_prompt,
    )

    class Prompt:
        name = "document-question"
        version = 4
        prompt = "Responde con evidencia."

    class Client:
        def __init__(self) -> None:
            self.calls: list[tuple[str, int, str]] = []

        def get_prompt(self, name: str, *, version: int, type: Literal["text"]) -> Prompt:
            self.calls.append((name, version, type))
            return Prompt()

    client = Client()
    definition = load_langfuse_prompt(client, name="document-question", version=4)

    assert client.calls == [("document-question", 4, "text")]
    assert definition.name == "document-question"
    assert definition.version == 4
    assert definition.content == "Responde con evidencia."
