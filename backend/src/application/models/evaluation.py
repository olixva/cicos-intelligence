"""Normalized outcome fields shared by the evaluation runner."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

_ROUTE_DECISIONS = frozenset({"question", "claim", "clarification_required"})


def _mapping(value: object) -> Mapping[str, object]:
    return cast(Mapping[str, object], value) if isinstance(value, Mapping) else {}


def _nonempty_text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _has_values(value: object) -> bool:
    return isinstance(value, (list, tuple)) and len(cast(Sequence[object], value)) > 0


@dataclass(frozen=True, slots=True)
class EvaluableTurn:
    """Separate the selected route from the result ultimately shown to a user."""

    route_decision: str | None
    result_kind: str | None
    needs_input: bool
    terminal_status: str | None
    technical_error: str | None

    @classmethod
    def from_envelope(cls, response: Mapping[str, object], requested_mode: str) -> EvaluableTurn:
        """Project an API envelope without collapsing routing and result kind."""

        metadata = _mapping(response.get("metadata"))
        result = _mapping(response.get("result"))
        result_kind = _nonempty_text(result.get("kind"))
        resolved_mode = _nonempty_text(response.get("resolved_mode"))

        route_decision: str | None = None
        provider_decision = metadata.get("decision")
        if isinstance(provider_decision, str) and provider_decision in _ROUTE_DECISIONS:
            route_decision = provider_decision
        elif requested_mode == "auto" and resolved_mode in {"question", "claim"}:
            route_decision = resolved_mode
        elif requested_mode in {"question", "claim"}:
            route_decision = requested_mode

        guardrail_blocked = metadata.get("guardrail") == "blocked"
        needs_input = (
            _has_values(result.get("missing_fields"))
            or _has_values(result.get("missing_information"))
            or (result_kind == "clarification" and not guardrail_blocked)
        )

        terminal_status = _nonempty_text(result.get("status")) or _nonempty_text(
            result.get("decision")
        )
        if terminal_status is None and result_kind == "clarification":
            terminal_status = "clarification"

        technical_error = _nonempty_text(response.get("code"))
        return cls(
            route_decision=route_decision,
            result_kind=result_kind,
            needs_input=needs_input,
            terminal_status=terminal_status,
            technical_error=technical_error,
        )

    @classmethod
    def from_error(cls, error: BaseException) -> EvaluableTurn:
        """Store an error class without copying provider bodies or secret text."""

        return cls(
            route_decision=None,
            result_kind=None,
            needs_input=False,
            terminal_status=None,
            technical_error=type(error).__name__,
        )
