"""Client for TypeSafe's Jev (System One) decision API.

Contrato tomado del OpenAPI público del SDK oficial (``typesafe-sdk``):
``POST {base}/v1/systemone`` con ``Authorization: Bearer``; cuerpo
``{model, state, questions}``; respuesta ``{model, answers, usage}``. Se usa
``httpx`` directamente en lugar del SDK: el contrato es pequeño y evita una
dependencia de un proveedor en acceso anticipado. Las variables de entorno
reproducen las del SDK (``TYPESAFE_API_KEY``, ``TYPESAFE_BASE_URL``,
``TYPESAFE_DEFAULT_MODEL``).

SIN VERIFICAR contra el servicio real: este módulo se escribió y probó con
dobles. Si el contrato difiere, es el único fichero a ajustar.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, cast

import httpx

from application.ports.outbound.decision_model import (
    Answer,
    ChoiceAnswer,
    DecisionResult,
    NoulAnswer,
    NoulQuestion,
    Question,
)
from application.ports.outbound.language_model import (
    LanguageModelError,
    MissingLanguageModelCredentialsError,
    ModelOutputError,
    ModelTimeoutError,
)

DEFAULT_BASE_URL = "https://api.typesafe.ai"
DEFAULT_MODEL = "jev-latest"
SYSTEM_ONE_PATH = "/v1/systemone"
_RETRY_STATUSES = frozenset({408, 429, *range(500, 600)})


class JevDecisionModel:
    """Typed decisions over Jev with bounded retries and strict response checks."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float = 10.0,
        max_retries: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("decision-model timeout must be positive")
        if max_retries < 0:
            raise ValueError("decision-model max_retries must not be negative")
        self._api_key = api_key
        self._base_url = (
            base_url or os.environ.get("TYPESAFE_BASE_URL") or DEFAULT_BASE_URL
        ).rstrip("/")
        self._model = model or os.environ.get("TYPESAFE_DEFAULT_MODEL") or DEFAULT_MODEL
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._transport = transport
        self._sleep = sleep

    @property
    def model(self) -> str:
        return self._model

    async def decide(
        self, state: str | Mapping[str, Any], questions: Mapping[str, Question]
    ) -> DecisionResult:
        if not questions:
            raise ValueError("at least one question is required")
        api_key = self._api_key or os.environ.get("TYPESAFE_API_KEY", "").strip()
        if not api_key:
            raise MissingLanguageModelCredentialsError("TYPESAFE_API_KEY is not configured")
        body = {
            "model": self._model,
            "state": state if isinstance(state, str) else dict(state),
            "questions": {name: _wire_question(question) for name, question in questions.items()},
        }
        payload = await self._post(body, api_key)
        return _parse_response(payload, questions)

    async def _post(self, body: dict[str, Any], api_key: str) -> object:
        headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
        async with httpx.AsyncClient(
            base_url=self._base_url, timeout=self._timeout, transport=self._transport
        ) as client:
            for attempt in range(self._max_retries + 1):
                last = attempt == self._max_retries
                try:
                    response = await client.post(SYSTEM_ONE_PATH, json=body, headers=headers)
                except httpx.TimeoutException as error:
                    if last:
                        raise ModelTimeoutError("decision model request timed out") from error
                    await self._sleep(_backoff(attempt, None))
                    continue
                except httpx.HTTPError as error:
                    if last:
                        raise LanguageModelError("decision model is unreachable") from error
                    await self._sleep(_backoff(attempt, None))
                    continue
                if response.status_code == 200:
                    try:
                        return cast(object, response.json())
                    except ValueError as error:
                        raise ModelOutputError("decision model returned invalid JSON") from error
                if response.status_code in _RETRY_STATUSES and not last:
                    await self._sleep(_backoff(attempt, response.headers))
                    continue
                # Sólo el estado HTTP: el cuerpo puede reflejar el estado enviado.
                raise LanguageModelError(
                    f"decision model request failed with HTTP {response.status_code}"
                )
        raise LanguageModelError("decision model request failed")  # pragma: no cover


def _backoff(attempt: int, headers: Mapping[str, str] | None) -> float:
    if headers is not None:
        try:
            if "retry-after-ms" in headers:
                return min(float(headers["retry-after-ms"]) / 1000, 10.0)
            if "retry-after" in headers:
                return min(float(headers["retry-after"]), 10.0)
        except ValueError:
            pass
    return min(0.5 * 2**attempt, 5.0)


def _wire_question(question: Question) -> dict[str, Any]:
    if isinstance(question, NoulQuestion):
        wire: dict[str, Any] = {"type": "noul", "instructions": question.instructions}
        criteria = {
            key: value
            for key, value in (("true", question.true), ("false", question.false))
            if value is not None
        }
        if criteria:
            wire["criteria"] = criteria
        return wire
    return {
        "type": "choice",
        "instructions": question.instructions,
        "criteria": dict(question.criteria),
    }


def _parse_response(payload: object, questions: Mapping[str, Question]) -> DecisionResult:
    if not isinstance(payload, dict):
        raise ModelOutputError("decision model returned an invalid response")
    body = cast(dict[str, Any], payload)
    raw_answers = body.get("answers")
    usage = body.get("usage")
    model = body.get("model")
    if not isinstance(raw_answers, dict) or not isinstance(model, str):
        raise ModelOutputError("decision model returned an invalid response")
    answers: dict[str, Answer] = {}
    for name, question in questions.items():
        raw = cast(dict[str, Any], raw_answers).get(name)
        answers[name] = _parse_answer(raw, question)
    tokens = cast(dict[str, Any], usage) if isinstance(usage, dict) else {}
    return DecisionResult(
        answers=answers,
        model=model,
        input_tokens=_count(tokens.get("input_tokens")),
        output_tokens=_count(tokens.get("output_tokens")),
    )


def _count(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _probability(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
        raise ModelOutputError("decision model returned an out-of-range probability")
    return float(value)


def _parse_answer(raw: object, question: Question) -> Answer:
    if not isinstance(raw, dict):
        raise ModelOutputError("decision model omitted an answer")
    answer = cast(dict[str, Any], raw)
    if isinstance(question, NoulQuestion):
        if answer.get("type") != "noul":
            raise ModelOutputError("decision model answered with the wrong type")
        return NoulAnswer(_probability(answer.get("noul")))
    if answer.get("type") != "choice":
        raise ModelOutputError("decision model answered with the wrong type")
    choice = answer.get("choice")
    probabilities = answer.get("probabilities")
    if not isinstance(choice, str) or choice not in question.criteria:
        raise ModelOutputError("decision model chose an option that was not offered")
    if not isinstance(probabilities, dict):
        raise ModelOutputError("decision model omitted option probabilities")
    parsed = {
        str(key): _probability(value)
        for key, value in cast(dict[object, object], probabilities).items()
    }
    return ChoiceAnswer(
        choice=choice,
        confidence=_probability(answer.get("confidence")),
        probabilities=parsed,
    )
