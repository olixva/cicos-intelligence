"""Common error response envelope for the unified API surface.

All three modes (question, claim, auto) and the streaming endpoint
share the same error shape so the frontend can render failures
consistently. Internal exception traces and provider messages are
deliberately excluded; the surface only exposes a stable ``code``, a
short ``message`` safe to log, the per-request identifier, and a
``retryable`` hint that drives client UX.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _ResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


ErrorCode = Literal[
    "invalid_request",
    "unsupported_profile",
    "unsupported_mode",
    "unsupported_language",
    "provider_timeout",
    "provider_unavailable",
    "internal_error",
]


class ErrorResponse(_ResponseModel):
    """One bounded failure response.

    The ``code`` literal is closed: the surface never invents new ones.
    ``insufficient_evidence`` is intentionally absent — that is a 200
    body status (``QuestionAnswer.status`` / ``ClaimAnalysis`` field),
    not an error code. The optional ``retryable`` hint is the only
    piece of UX guidance the surface emits; the client decides how to
    act on it.
    """

    code: ErrorCode
    message: str = Field(max_length=200)
    request_id: str
    retryable: bool


def error_response_for(
    code: ErrorCode, message: str, request_id: str, retryable: bool
) -> ErrorResponse:
    """Build an ``ErrorResponse`` while keeping the literal closed.

    Centralised so the surface has exactly one place that knows the
    closed ``code`` enumeration; callers pass the code as a string and
    the constructor validates it.
    """

    return ErrorResponse(code=code, message=message, request_id=request_id, retryable=retryable)
