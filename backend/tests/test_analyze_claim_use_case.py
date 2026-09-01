"""The claim input port delegates unchanged user facts to its workflow."""

import asyncio
from dataclasses import dataclass

from application.models.claim import ClaimExecution
from domain.models.claim import ClaimInput
from domain.models.decision import ClaimAnalysis


@dataclass
class _Workflow:
    received: list[ClaimInput]

    async def run(self, claim: ClaimInput) -> ClaimExecution:
        self.received.append(claim)
        return ClaimExecution(
            result=ClaimAnalysis(
                applicability="undetermined",
                convention=None,
                decision="undetermined",
                party_ids=(),
                facts=(),
                contradictions=(),
                conditions=(),
                missing_information=("Describir los vehículos implicados.",),
                blocks=(),
            ),
            context=(),
        )


def test_analyze_claim_delegates_the_unchanged_input() -> None:
    from application.use_cases.analyze_claim_use_case import AnalyzeClaimUseCase

    workflow = _Workflow(received=[])
    claim = ClaimInput("Vehículo A y vehículo B colisionan.", clarifications=("Fue en ciudad.",))

    execution = asyncio.run(AnalyzeClaimUseCase(workflow).execute(claim))

    assert workflow.received == [claim]
    assert execution.result.decision == "undetermined"
