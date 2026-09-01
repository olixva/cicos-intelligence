"""Boundary for structured extraction of attributed claim facts."""

from collections.abc import Awaitable
from typing import Protocol

from application.models.claim import ExtractedClaimFacts
from domain.models.claim import ClaimInput


class ClaimFactExtractor(Protocol):
    """Extract observations from the supplied claim, never from manual context."""

    def extract(self, claim: ClaimInput) -> Awaitable[ExtractedClaimFacts]: ...
