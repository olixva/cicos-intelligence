"""LangGraph claim workflow keeps facts attributable and gates outcomes by evidence."""

import asyncio
from dataclasses import dataclass

from application.models.claim import ClaimExecution, ExtractedClaimFacts
from application.models.retrieval import Chunk
from application.ports.outbound.claim_fact_extractor import ClaimFactExtractor
from application.ports.outbound.evidence_reader import EvidenceReader
from application.ports.outbound.retriever import RetrievalRequest, Retriever
from domain.models.claim import ClaimFact, ClaimInput
from domain.models.evidence import PageEvidence


@dataclass
class _Extractor(ClaimFactExtractor):
    result: ExtractedClaimFacts

    async def extract(self, claim: ClaimInput) -> ExtractedClaimFacts:
        return self.result


class _Retriever(Retriever):
    async def retrieve(self, request: RetrievalRequest) -> tuple[Chunk, ...]:
        assert request.limit == 6
        return (Chunk("criteria", "El Convenio exige dos vehículos.", ("manual:page:56",)),)


@dataclass
class _Evidence(EvidenceReader):
    page: PageEvidence

    def get(self, evidence_id: str) -> PageEvidence:
        assert evidence_id == self.page.evidence_id
        return self.page


def test_claim_graph_preserves_conflicting_attributions_and_gates_inapplicable_case() -> None:
    from infrastructure.adapters.outbound.claim_workflow.langgraph_workflow import (
        LangGraphClaimWorkflow,
    )

    facts = (
        ClaimFact("vehicle_count", "3", None, "intervienen tres vehículos"),
        ClaimFact("traffic_light", "verde", "A", "A dice verde"),
        ClaimFact("traffic_light", "rojo", "B", "B dice rojo"),
    )
    workflow = LangGraphClaimWorkflow(
        fact_extractor=_Extractor(ExtractedClaimFacts(("A", "B"), facts)),
        retriever=_Retriever(),
        evidence_repository=_Evidence(
            PageEvidence("manual:page:56", "a" * 64, 56, "texto", None, None, ())
        ),
    )

    execution: ClaimExecution = asyncio.run(
        workflow.run(ClaimInput("A dice verde; B dice rojo; intervienen tres vehículos."))
    )

    assert execution.result.applicability == "not_applicable"
    assert execution.result.decision == "not_assessed"
    assert execution.result.contradictions[0].fact_name == "traffic_light"
    contradiction_values = {fact.value for fact in execution.result.contradictions[0].statements}
    assert contradiction_values == {"verde", "rojo"}
    assert execution.result.blocks[0].evidence_ids == ("manual:page:56",)
    assert execution.context[0].evidence_ids == ("manual:page:56",)


def test_claim_graph_requests_missing_prerequisites_without_inventing_a_conclusion() -> None:
    from infrastructure.adapters.outbound.claim_workflow.langgraph_workflow import (
        LangGraphClaimWorkflow,
    )

    workflow = LangGraphClaimWorkflow(
        fact_extractor=_Extractor(ExtractedClaimFacts(("A", "B"), ())),
        retriever=_Retriever(),
        evidence_repository=_Evidence(
            PageEvidence("manual:page:56", "a" * 64, 56, "texto", None, None, ())
        ),
    )

    execution = asyncio.run(workflow.run(ClaimInput("Hubo un accidente entre A y B.")))

    assert execution.needs_input is True
    assert execution.thread_id
    assert execution.missing_information
    assert execution.result.applicability == "undetermined"
    assert execution.result.decision == "conditional"
    assert "cuántos vehículos" in execution.result.conditions[0]
