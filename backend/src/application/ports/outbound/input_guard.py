"""Outbound port for a semantic input check that runs before any workflow."""

from collections.abc import Awaitable
from typing import Protocol


class InputGuard(Protocol):
    """Return a user-facing refusal for input that must not reach the workflows, else ``None``."""

    def check(self, text: str) -> Awaitable[str | None]: ...
