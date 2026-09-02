"""OpenAI structured-output adapter for attributed claim facts."""

from __future__ import annotations

import json
import os
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Protocol, cast

from langfuse.openai import AsyncOpenAI  # pyright: ignore[reportPrivateImportUsage]
from openai import APIError, APITimeoutError
from openai.types.responses import ResponseInputParam
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from application.models.claim import ExtractedClaimFacts
from application.ports.outbound.claim_fact_extractor import ClaimFactExtractor
from application.ports.outbound.language_model import (
    LanguageModelError,
    MissingLanguageModelCredentialsError,
    ModelOutputError,
    ModelTimeoutError,
)
from domain.models.claim import ClaimFact, ClaimInput


class _StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ClaimFactSchema(_StrictSchema):
    name: str = Field(min_length=1)
    value: str | None = None
    asserted_by: str | None = None
    source_text: str = Field(min_length=1)


class ClaimExtractionSchema(_StrictSchema):
    party_ids: tuple[str, ...]
    facts: tuple[ClaimFactSchema, ...]

    def to_application(self) -> ExtractedClaimFacts:
        return ExtractedClaimFacts(
            self.party_ids,
            tuple(
                ClaimFact(item.name, item.value, item.asserted_by, item.source_text)
                for item in self.facts
            ),
        )


class ParsedResponseView(Protocol):
    @property
    def output_parsed(self) -> object | None: ...

    @property
    def status(self) -> str: ...


class ClaimResponsesTransport(Protocol):
    def parse(
        self,
        *,
        model: str,
        input: ResponseInputParam,
        text_format: type[ClaimExtractionSchema],
        store: bool,
        timeout: float,
    ) -> Awaitable[ParsedResponseView]: ...


class _OpenAIClaimResponsesTransport:
    def __init__(self, api_key: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key, max_retries=0)

    async def parse(
        self,
        *,
        model: str,
        input: ResponseInputParam,
        text_format: type[ClaimExtractionSchema],
        store: bool,
        timeout: float,
    ) -> ParsedResponseView:
        response = await self._client.responses.parse(
            model=model, input=input, text_format=text_format, store=store, timeout=timeout
        )
        return cast(ParsedResponseView, response)


@dataclass
class OpenAIClaimFactExtractor(ClaimFactExtractor):
    """Extract only observations explicitly contained in a claim and clarifications."""

    model: str
    api_key: str | None = None
    transport: ClaimResponsesTransport | None = None
    timeout_seconds: float = 20.0
    #: Nombres de hecho que el ruleset firmado consulta.
    fact_names: tuple[str, ...] = ()

    async def extract(self, claim: ClaimInput) -> ExtractedClaimFacts:
        if not self.model.strip():
            raise ValueError("claim extraction model must be nonempty")
        if self.timeout_seconds <= 0:
            raise ValueError("claim extraction timeout must be positive")
        try:
            response = await self._transport_for_request().parse(
                model=self.model,
                input=_messages(claim, self.fact_names),
                text_format=ClaimExtractionSchema,
                store=False,
                timeout=self.timeout_seconds,
            )
        except (APITimeoutError, TimeoutError) as error:
            raise ModelTimeoutError("claim fact extraction timed out") from error
        except (ValidationError, ValueError) as error:
            raise ModelOutputError("provider returned invalid claim facts") from error
        except APIError as error:
            raise LanguageModelError("claim fact provider request failed") from error
        if response.status == "incomplete" or response.output_parsed is None:
            raise ModelOutputError("provider returned no usable claim facts")
        if not isinstance(response.output_parsed, ClaimExtractionSchema):
            raise ModelOutputError("provider returned invalid claim facts")
        try:
            return response.output_parsed.to_application()
        except (ValidationError, ValueError) as error:
            raise ModelOutputError("provider returned invalid claim facts") from error

    def _transport_for_request(self) -> ClaimResponsesTransport:
        if self.transport is not None:
            return self.transport
        api_key = self.api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise MissingLanguageModelCredentialsError("OPENAI_API_KEY is not configured")
        self.transport = _OpenAIClaimResponsesTransport(api_key)
        return self.transport


def _messages(claim: ClaimInput, fact_names: tuple[str, ...] = ()) -> ResponseInputParam:
    # Los nombres estables se derivan del ruleset firmado, no se escriben aquí:
    # una regla no puede depender de un hecho que nadie pidió extraer.
    stable = (
        ", ".join(fact_names)
        if fact_names
        else ("vehicle_count, direct_collision, third_vehicle_identified, chain_collision")
    )
    developer = (
        "Extrae únicamente hechos contenidos en el relato. Conserva la atribución y el "
        "texto literal de cada afirmación. No resuelvas responsabilidad, no inventes "
        "valores y no uses conocimiento externo. "
        f"Usa estos nombres estables cuando apliquen: {stable}. "
        "Para booleanos usa los literales true o false.\n"
        "Contar lo que el relato describe NO es inventar:\n"
        "- vehicle_count: número de vehículos que el relato identifica como intervinientes. "
        "Un relato que nombra al vehículo A y al vehículo B da vehicle_count=2. Un vehículo "
        "no identificado que se da a la fuga no cuenta como interviniente identificado.\n"
        "- direct_collision: true si el relato describe un choque entre los vehículos "
        "intervinientes; false sólo si el relato dice que no lo hubo.\n"
        "- chain_collision: true si el relato describe una secuencia de colisiones "
        "encadenada sin interrupción.\n"
        "- third_vehicle_identified: true sólo si el relato identifica un tercer vehículo.\n"
        "- driver_under_influence: true si el relato menciona alcohol, drogas o "
        "estupefacientes en alguno de los conductores.\n"
        "Si el relato no permite establecer un hecho, omítelo: no lo supongas."
    )
    payload = json.dumps(
        {"claim": claim.text, "clarifications": claim.clarifications, "language": claim.language},
        ensure_ascii=False,
        sort_keys=True,
    )
    return cast(
        ResponseInputParam,
        [
            {"role": "developer", "content": developer},
            {"role": "user", "content": f"<claim_data>{payload}</claim_data>"},
        ],
    )
