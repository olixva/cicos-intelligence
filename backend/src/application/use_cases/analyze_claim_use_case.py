"""Application entry point for convention claim analysis."""

from dataclasses import dataclass

from application.models.claim import ClaimExecution
from application.ports.outbound.claim_workflow import ClaimWorkflow
from domain.models.claim import ClaimInput


@dataclass(frozen=True, slots=True)
class AnalyzeClaimUseCase:
    """Delegate claim orchestration through the workflow port."""

    workflow: ClaimWorkflow

    async def execute(self, claim: ClaimInput) -> ClaimExecution:
        return await self.workflow.run(claim)
