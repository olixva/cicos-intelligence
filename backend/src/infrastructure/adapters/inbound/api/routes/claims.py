"""Explicit HTTP endpoint for source-grounded convention-claim analysis."""

from __future__ import annotations

from fastapi import APIRouter

from application.ports.inbound.analyze_claim import AnalyzeClaim
from domain.models.claim import ClaimInput
from infrastructure.adapters.inbound.api.schemas.claim import (
    ClaimAnalysisRequest,
    ClaimAnalysisResponse,
)


def build_claim_router(analyze_claim: AnalyzeClaim) -> APIRouter:
    """Bind the claim route solely to its inbound application port."""

    router = APIRouter(prefix="/api/v1/claims", tags=["claims"])

    async def analyze_claim_route(request: ClaimAnalysisRequest) -> ClaimAnalysisResponse:
        clarifications = tuple(request.clarifications) if request.clarifications else ()
        claim = ClaimInput(
            text=request.text, language=request.language, clarifications=clarifications
        )
        execution = await analyze_claim.execute(claim)
        return ClaimAnalysisResponse.from_domain(execution)

    router.add_api_route(
        "/analyze",
        analyze_claim_route,
        methods=["POST"],
        response_model=ClaimAnalysisResponse,
    )
    return router
