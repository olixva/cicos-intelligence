"""Outbound orchestration boundary for the claim-analysis graph."""

from collections.abc import Awaitable
from typing import Protocol

from application.models.claim import ClaimExecution
from domain.models.claim import ClaimInput


class ClaimWorkflow(Protocol):
    """Coordinate claim stages behind the application boundary."""

    def run(self, claim: ClaimInput) -> Awaitable[ClaimExecution]: ...
