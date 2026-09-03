"""Adaptadores OpenAI: generacion, extraccion de hechos y embeddings."""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx
import pytest
from openai import RateLimitError
from openai.types import CreateEmbeddingResponse
from openai.types.create_embedding_response import Usage
from openai.types.embedding import Embedding
from openai.types.responses import ResponseInputParam

from application.models.query import AnswerBlock, ContextEvidence, QueryInput, QuestionAnswer
from application.ports.outbound.language_model import ModelOutputError, ModelTimeoutError
from domain.models.claim import ClaimInput
from domain.models.evidence import PageEvidence
from domain.rules.ruleset import fact_names
from infrastructure.adapters.outbound.language_model.openai_claim_fact_extractor import (
    OpenAIClaimFactExtractor,
    _messages,  # pyright: ignore[reportPrivateUsage]
)
from infrastructure.adapters.outbound.language_model.openai_language_model import (
    AnswerSchema,
    ParsedResponseView,
)
from infrastructure.config.rules_artifacts import load_rules_artifacts

# --------------------------------------------------------------------------
# OpenAI Responses structured-output boundary tests with no network calls.
# --------------------------------------------------------------------------


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


# --------------------------------------------------------------------------
# OpenAI claim extractor sends only the original claim and maps typed output.
# --------------------------------------------------------------------------


@dataclass
class _Response:
    output_parsed: object | None
    status: str = "completed"


class _Transport:
    captured_input: object | None = None

    async def parse(self, **kwargs: object) -> _Response:
        self.captured_input = kwargs["input"]
        from infrastructure.adapters.outbound.language_model.openai_claim_fact_extractor import (
            ClaimExtractionSchema,
            ClaimFactSchema,
        )

        return _Response(
            ClaimExtractionSchema(
                party_ids=("A", "B"),
                facts=(
                    ClaimFactSchema(
                        name="vehicle_count",
                        value="3",
                        asserted_by=None,
                        source_text="intervienen tres vehículos",
                    ),
                ),
            )
        )


def test_claim_extraction_to_application_drops_whitespace_only_facts_and_questions() -> None:
    """El proveedor a veces emite ``name`` o ``source_text`` whitespace-only en
    un fact, e ``id``/``prompt``/``reason`` whitespace-only en una pregunta. El
    invariante de no-vacío lo aplica el dataclass (`` `` ``.strip()`` `` `` no
    vacío), no Pydantic ``min_length=1``. El adaptador debe descartar los
    inválidos antes de cruzar al modelo de aplicación en lugar de propagar
    ``ValueError`` que tira la request con 500."""

    from infrastructure.adapters.outbound.language_model.openai_claim_fact_extractor import (
        ClaimExtractionSchema,
        ClaimFactSchema,
        InterviewQuestionSchema,
    )

    parsed = ClaimExtractionSchema(
        party_ids=("A", "B"),
        facts=(
            ClaimFactSchema(
                name="vehicle_count",
                value="2",
                asserted_by=None,
                source_text="dos vehículos",
            ),
            ClaimFactSchema(
                name="   ",  # whitespace-only, Pydantic min_length=1 pasa
                value="x",
                asserted_by=None,
                source_text="  \n  ",
            ),
            ClaimFactSchema(
                name="direct_collision",
                value=None,
                asserted_by=None,
                source_text="   ",  # whitespace-only — Pydantic pasa, dataclass rechaza
            ),
        ),
        interview_status="ask",
        questions=(
            InterviewQuestionSchema(
                id="q1",
                prompt="¿quién circulaba?",
                reason="aporta la norma",
            ),
            InterviewQuestionSchema(
                id="  ",
                prompt="\t\n",
                reason=" ",
            ),
        ),
    )

    application = parsed.to_application()

    assert len(application.facts) == 1
    assert application.facts[0].name == "vehicle_count"

    assert application.interview_plan.status == "ask"
    assert len(application.interview_plan.questions) == 1
    assert application.interview_plan.questions[0].id == "q1"


def test_known_boolean_fact_coerces_arbitrary_value_to_strict_boolean() -> None:
    """Bug D: el extractor emite ``value="A"`` para ``one_vehicle_parked`` cuando
    el LLM lo confunde con un identificador de vehículo. El adaptador debe
    normalizar cualquier valor presente al literal estricto ``"true"`` para
    nombres booleanos conocidos — la presencia del fact ya implica que la
    maniobra ocurre."""

    from infrastructure.adapters.outbound.language_model.openai_claim_fact_extractor import (
        ClaimExtractionSchema,
        ClaimFactSchema,
    )

    parsed = ClaimExtractionSchema(
        party_ids=("A", "B"),
        facts=(
            ClaimFactSchema(
                name="one_vehicle_parked",
                value="A",
                asserted_by=None,
                source_text="uno de los vehículos estaba estacionado",
            ),
        ),
    )

    application = parsed.to_application()

    assert len(application.facts) == 1
    assert application.facts[0].name == "one_vehicle_parked"
    assert application.facts[0].value == "true"


def test_known_boolean_fact_normalises_string_true_false() -> None:
    """Para nombres booleanos conocidos, los literales canónicos y sus alias
    (``"true"``, ``"sí"``, ``"yes"``, ``"1"`` / ``"false"``, ``"no"``, ``"0"``)
    se reducen al literal estricto."""

    from infrastructure.adapters.outbound.language_model.openai_claim_fact_extractor import (
        ClaimExtractionSchema,
        ClaimFactSchema,
    )

    parsed = ClaimExtractionSchema(
        party_ids=("A", "B"),
        facts=(
            ClaimFactSchema(
                name="direct_collision",
                value="true",
                asserted_by=None,
                source_text="relato describe choque",
            ),
            ClaimFactSchema(
                name="direct_collision",
                value="false",
                asserted_by=None,
                source_text="relato dice que no lo hubo",
            ),
            ClaimFactSchema(
                name="direct_collision",
                value="sí",
                asserted_by=None,
                source_text="el conductor afirma que sí",
            ),
            ClaimFactSchema(
                name="direct_collision",
                value="yes",
                asserted_by=None,
                source_text="yes there was a collision",
            ),
        ),
    )

    application = parsed.to_application()
    values = tuple(fact.value for fact in application.facts)

    assert values == ("true", "false", "true", "true")


def test_known_boolean_fact_with_none_value_becomes_false() -> None:
    """Un fact booleano conocido sin valor (ausente o ``None``) representa la
    ausencia del hecho en el relato y se normaliza a ``"false"``."""

    from infrastructure.adapters.outbound.language_model.openai_claim_fact_extractor import (
        ClaimExtractionSchema,
        ClaimFactSchema,
    )

    parsed = ClaimExtractionSchema(
        party_ids=("A", "B"),
        facts=(
            ClaimFactSchema(
                name="one_vehicle_parked",
                value=None,
                asserted_by=None,
                source_text="el relato no menciona vehículo estacionado",
            ),
        ),
    )

    application = parsed.to_application()

    assert application.facts[0].value == "false"


def test_unknown_fact_passes_value_through_unchanged() -> None:
    """Los facts cuyo nombre no es booleano conocido pasan tal cual — no se
    fuerza coerción. ``lane_change_vehicle`` es un identificador de vehículo,
    no un booleano."""

    from infrastructure.adapters.outbound.language_model.openai_claim_fact_extractor import (
        ClaimExtractionSchema,
        ClaimFactSchema,
    )

    parsed = ClaimExtractionSchema(
        party_ids=("A", "B"),
        facts=(
            ClaimFactSchema(
                name="lane_change_vehicle",
                value="A",
                asserted_by=None,
                source_text="ambos coinciden en que el A cambiaba de carril",
            ),
        ),
    )

    application = parsed.to_application()

    assert application.facts[0].value == "A"


def test_string_fact_is_not_coerced() -> None:
    """Los facts con semántica string (no booleano) preservan su valor exacto,
    p. ej. ``vehicle_count`` que ya en el prompt se documenta como número."""

    from infrastructure.adapters.outbound.language_model.openai_claim_fact_extractor import (
        ClaimExtractionSchema,
        ClaimFactSchema,
    )

    parsed = ClaimExtractionSchema(
        party_ids=("A", "B"),
        facts=(
            ClaimFactSchema(
                name="vehicle_count",
                value="3",
                asserted_by=None,
                source_text="intervienen tres vehículos",
            ),
        ),
    )

    application = parsed.to_application()

    assert application.facts[0].value == "3"


def test_claim_extractor_uses_structured_output_and_never_adds_manual_context() -> None:
    from infrastructure.adapters.outbound.language_model.openai_claim_fact_extractor import (
        OpenAIClaimFactExtractor,
    )

    transport = _Transport()
    result = asyncio.run(
        OpenAIClaimFactExtractor(model="gpt-4.1-mini", transport=transport).extract(
            ClaimInput("A informa que intervienen tres vehículos.", clarifications=("B discrepa.",))
        )
    )

    assert result.party_ids == ("A", "B")
    assert result.facts[0].name == "vehicle_count"
    rendered = str(transport.captured_input)
    assert "tres vehículos" in rendered
    assert "context" not in rendered.lower()


def test_claim_extractor_instructs_the_model_to_return_a_bounded_interview_plan() -> None:
    from infrastructure.adapters.outbound.language_model.openai_claim_fact_extractor import (
        _messages,
    )

    rendered = str(_messages(ClaimInput("A y B chocaron.")))

    assert "plan de entrevista" in rendered.lower()
    assert "no repitas" in rendered.lower()
    assert "matriculación" in rendered.lower()


# --------------------------------------------------------------------------
# The extractor must be asked for exactly the facts the ruleset reads.
#
# The prompt used to hardcode four names while the signed ruleset consulted
# more. The alcohol rule, whose whole purpose is to stop a wrong exclusion,
# could never fire because nothing ever extracted `driver_under_influence`.
# --------------------------------------------------------------------------


_RULES = load_rules_artifacts(Path(__file__).resolve().parents[2] / "data" / "rules").rules


def test_fact_names_are_derived_from_the_rules_that_read_them() -> None:
    names = fact_names(_RULES)
    assert "vehicle_count" in names
    assert "chain_collision" in names
    # La regla de no exclusión por alcoholemia lee este hecho.
    assert "driver_under_influence" in names


def test_the_prompt_asks_for_every_fact_the_ruleset_consults() -> None:
    from domain.models.claim import ClaimInput

    extractor = OpenAIClaimFactExtractor(model="m", fact_names=fact_names(_RULES))
    developer = _messages(ClaimInput("relato"), extractor.fact_names)[0]["content"]
    for name in fact_names(_RULES):
        assert name in developer, f"the prompt never asks for {name}"


def test_the_prompt_still_forbids_inventing_values() -> None:
    from domain.models.claim import ClaimInput

    developer = _messages(ClaimInput("relato"), ("vehicle_count",))[0]["content"]
    assert "no inventes" in developer.lower()


# --------------------------------------------------------------------------
# OpenAI embedding boundary tests with typed, fully local transports.
# --------------------------------------------------------------------------


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
