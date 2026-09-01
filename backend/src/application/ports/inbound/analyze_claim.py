"""Inbound port for source-grounded convention analysis."""

from collections.abc import Awaitable
from typing import Protocol

from application.models.claim import ClaimExecution
from domain.models.claim import ClaimInput


class AnalyzeClaim(Protocol):
    """Analyze a claim without presenting a general liability opinion."""

    def execute(self, claim: ClaimInput) -> Awaitable[ClaimExecution]: ...
