"""LangGraph claim workflow keeps facts attributable and gates outcomes by evidence."""

import asyncio
from dataclasses import dataclass

from application.models.claim import (
    ClaimExecution,
    ExtractedClaimFacts,
    InterviewPlan,
    InterviewQuestion,
)
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


class _InterviewExtractor(ClaimFactExtractor):
    async def extract(self, claim: ClaimInput) -> ExtractedClaimFacts:
        if not claim.clarifications:
            return ExtractedClaimFacts(
                ("A", "B"),
                (ClaimFact("vehicle_count", "2", None, "dos vehículos"),),
                InterviewPlan(
                    "ask",
                    (
                        InterviewQuestion(
                            id="direct_collision",
                            prompt="¿Hubo colisión directa?",
                            reason="Es necesaria para comprobar el ámbito.",
                            answer_kind="boolean",
                        ),
                    ),
                ),
            )
        return ExtractedClaimFacts(
            ("A", "B"),
            (
                ClaimFact("vehicle_count", "2", None, "dos vehículos"),
                ClaimFact("direct_collision", "true", None, "sí, choque directo"),
                ClaimFact("maneuver_a", "detenido", "A", "A estaba detenido"),
            ),
            InterviewPlan("ready"),
        )


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


def test_claim_graph_uses_the_llm_interview_question_before_emitting_a_result() -> None:
    from infrastructure.adapters.outbound.claim_workflow.langgraph_workflow import (
        LangGraphClaimWorkflow,
    )

    question = InterviewQuestion(
        id="vehicle_a_signal",
        prompt="¿Qué color tenía el semáforo del vehículo A?",
        reason="La señal puede cambiar la prioridad.",
        answer_kind="choice",
        options=("Rojo", "Ámbar", "Verde", "No se sabe"),
    )
    workflow = LangGraphClaimWorkflow(
        fact_extractor=_Extractor(
            ExtractedClaimFacts(
                ("A", "B"),
                (ClaimFact("vehicle_count", "2", None, "dos vehículos"),),
                InterviewPlan("ask", (question,)),
            )
        ),
        retriever=_Retriever(),
        evidence_repository=_Evidence(
            PageEvidence("manual:page:56", "a" * 64, 56, "texto", None, None, ())
        ),
    )

    execution = asyncio.run(workflow.run(ClaimInput("Dos vehículos chocaron en un cruce.")))

    assert execution.needs_input is True
    assert execution.missing_information == (question.prompt,)


def test_claim_graph_exposes_a_dedicated_interview_planning_node() -> None:
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

    assert "plan_interview" in workflow._graph.get_graph().nodes  # pyright: ignore[reportPrivateUsage]


def test_claim_graph_resumes_after_an_answer_without_repeating_the_question() -> None:
    from infrastructure.adapters.outbound.claim_workflow.langgraph_workflow import (
        LangGraphClaimWorkflow,
    )

    workflow = LangGraphClaimWorkflow(
        fact_extractor=_InterviewExtractor(),
        retriever=_Retriever(),
        evidence_repository=_Evidence(
            PageEvidence("manual:page:56", "a" * 64, 56, "texto", None, None, ())
        ),
    )
    first = asyncio.run(workflow.run(ClaimInput("Dos vehículos tuvieron un accidente.")))
    resumed = asyncio.run(
        workflow.run(
            ClaimInput(
                "Dos vehículos tuvieron un accidente.",
                clarifications=("Sí, hubo colisión directa.",),
                thread_id=first.thread_id,
                resume=True,
            )
        )
    )

    assert first.needs_input is True
    assert resumed.needs_input is False


def test_claim_graph_surfaces_a_coverage_gap_without_asking_again() -> None:
    from infrastructure.adapters.outbound.claim_workflow.langgraph_workflow import (
        LangGraphClaimWorkflow,
    )

    workflow = LangGraphClaimWorkflow(
        fact_extractor=_Extractor(
            ExtractedClaimFacts(
                ("A", "B"),
                (
                    ClaimFact("vehicle_count", "2", None, "dos vehículos"),
                    ClaimFact("direct_collision", "true", None, "choque directo"),
                    ClaimFact("traffic_light", "rojo", "A", "A tenía rojo"),
                ),
                InterviewPlan(
                    "coverage_gap",
                    terminal_reason=(
                        "El manual indexado no contiene una regla verificable para estas versiones."
                    ),
                ),
            )
        ),
        retriever=_Retriever(),
        evidence_repository=_Evidence(
            PageEvidence("manual:page:56", "a" * 64, 56, "texto", None, None, ())
        ),
    )

    execution = asyncio.run(workflow.run(ClaimInput("Dos vehículos chocaron en un cruce.")))

    assert execution.needs_input is False
    assert execution.result.blocks[0].text.startswith("El manual indexado")
