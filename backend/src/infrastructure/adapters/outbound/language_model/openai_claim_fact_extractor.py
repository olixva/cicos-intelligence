"""OpenAI structured-output adapter for attributed claim facts."""

from __future__ import annotations

import json
import os
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Literal, Protocol, cast

from langfuse.openai import AsyncOpenAI  # pyright: ignore[reportPrivateImportUsage]
from openai import APIError, APITimeoutError
from openai.types.responses import ResponseInputParam
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from application.models.claim import ExtractedClaimFacts, InterviewPlan, InterviewQuestion
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


class InterviewQuestionSchema(_StrictSchema):
    id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    answer_kind: Literal["text", "choice", "boolean"] = "text"
    options: tuple[str, ...] = ()


class ClaimExtractionSchema(_StrictSchema):
    party_ids: tuple[str, ...]
    facts: tuple[ClaimFactSchema, ...]
    interview_status: Literal["ask", "ready", "inconsistent", "coverage_gap"] = "ready"
    questions: tuple[InterviewQuestionSchema, ...] = ()
    terminal_reason: str | None = None

    def to_application(self) -> ExtractedClaimFacts:
        return ExtractedClaimFacts(
            self.party_ids,
            tuple(
                ClaimFact(item.name, item.value, item.asserted_by, item.source_text)
                for item in self.facts
            ),
            InterviewPlan(
                status=self.interview_status,
                questions=tuple(
                    InterviewQuestion(
                        id=item.id,
                        prompt=item.prompt,
                        reason=item.reason,
                        answer_kind=item.answer_kind,
                        options=item.options,
                    )
                    for item in self.questions
                ),
                terminal_reason=self.terminal_reason,
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
        "- lane_change_acknowledged_by_both: true si ambos relatos (o el relato y las "
        "aclaraciones) coinciden en que uno de los vehículos cambiaba de carril, aunque "
        "discrepen sobre a quién corresponde la culpa.\n"
        "- contradictory_versions: true si los conductores dan versiones distintas sobre "
        "la responsabilidad del mismo hecho.\n"
        "- lane_change_vehicle: el identificador del vehículo (p. ej. A o B) que el relato "
        "describe cambiando de carril, sólo si ambas versiones coinciden en cuál era.\n"
        "Los hechos de maniobra describen SÓLO la maniobra que el relato narra. Omítelos si "
        "esa maniobra no aparece: por ejemplo, exit_manoeuvre_by exige una salida de "
        "estacionamiento, garaje o vía cortada; one_vehicle_parked exige un vehículo "
        "estacionado (un vehículo detenido ante un semáforo NO está aparcado); "
        "admitted_amber exige que un conductor admita pasar en ámbar. Rellenar uno de estos "
        "nombres porque el vehículo existe, y no porque la maniobra ocurra, es inventar.\n"
        "- daa_box_a / daa_box_b: el código de casilla (A0-A17 / B0-B17) del apartado 12 de "
        "la D.A.A. ÚNICAMENTE si el relato declara explícitamente qué casilla marcó cada "
        "conductor (p. ej. «en el parte marcamos A2 y B4»). Nunca traduzcas una descripción "
        "de la maniobra a un código de casilla por tu cuenta: eso es inventar, no extraer.\n"
        "- daa_section_12_only: true sólo si el relato dice explícitamente que la D.A.A. "
        "tiene cumplimentado únicamente el apartado 12 (sin atestado, verificación ocular ni "
        "testigos reconocidos por ambas partes).\n"
        "- door_opened_by / unpaved_road_by: el identificador del vehículo cuyo conductor "
        "abrió una puerta, o que circulaba por una vía sin pavimentar, sólo si el relato lo "
        "afirma explícitamente.\n"
        "Si el relato no permite establecer un hecho, omítelo: no lo supongas."
        "\nAdemás devuelve un plan de entrevista. Usa `ask` sólo si falta un hecho "
        "que pueda cambiar la aplicabilidad o permitir aplicar una regla del manual; "
        "formula entre una y tres preguntas concretas, comprensibles y no pidas "
        "casillas internas de formularios. Usa `ready` cuando no falte ningún hecho "
        "material para evaluar; `inconsistent` sólo para versiones incompatibles; y "
        "`coverage_gap` si los hechos están completos pero el manual no aporta una "
        "regla para resolver. No repitas preguntas ya contestadas en clarifications."
        " No preguntes por país del accidente, matriculación, adhesión de las "
        "aseguradoras ni requisitos administrativos salvo que el relato aporte un "
        "hecho que los ponga en duda: para esta entrevista son supuestos administrativos, "
        "no hechos que deban bloquear una conclusión sobre el manual."
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
