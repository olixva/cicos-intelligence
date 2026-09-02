"""El flujo de siniestros tiene que llegar a la tabla de culpabilidad CIDE.

La tabla estaba transcrita y atestada, y `lookup_daa_matrix` probado, pero el
grafo nunca la consultaba: un siniestro con las casillas del apartado 12
declaradas se quedaba en «Convenio aplicable, culpabilidad sin determinar»
para siempre. Estas pruebas fijan el recorrido completo y, sobre todo, dónde
NO debe resolver.
"""

import asyncio
from dataclasses import dataclass

from application.models.claim import ClaimExecution, ExtractedClaimFacts, InterviewPlan
from application.models.retrieval import Chunk
from application.ports.outbound.claim_fact_extractor import ClaimFactExtractor
from application.ports.outbound.evidence_reader import EvidenceReader
from application.ports.outbound.retriever import RetrievalRequest, Retriever
from domain.models.claim import ClaimFact, ClaimInput, MatrixCell
from domain.models.evidence import PageEvidence
from domain.rules.cide_matrix import MatrixException
from domain.rules.ruleset import LoadedRule
from infrastructure.adapters.outbound.claim_workflow.langgraph_workflow import (
    LangGraphClaimWorkflow,
)

_PAGE_101 = "sha256:" + "b" * 64 + ":page:101"


@dataclass
class _Extractor(ClaimFactExtractor):
    result: ExtractedClaimFacts

    async def extract(self, claim: ClaimInput) -> ExtractedClaimFacts:
        return self.result


class _Retriever(Retriever):
    async def retrieve(self, request: RetrievalRequest) -> tuple[Chunk, ...]:
        return (Chunk("criteria", "Tabla de culpabilidad CIDE.", ("manual:page:56",)),)


@dataclass
class _Evidence(EvidenceReader):
    page: PageEvidence

    def get(self, evidence_id: str) -> PageEvidence:
        return self.page


_MATRIX_RULE = LoadedRule(
    rule_id="cide-matrix-lookup",
    kind="matrix_lookup",
    description="Tabla de culpabilidad CIDE.",
    prerequisites=("daa_box_a", "daa_box_b", "daa_section_12_only"),
    outcome="Las cruces marcadas determinan la responsabilidad según la tabla.",
    evidence_ids=(_PAGE_101,),
    convention="CIDE",
)

_CELLS = {
    (2, 9): MatrixCell(2, 9, "B", (_PAGE_101,)),  # A1 + B8 → culpable B
    (1, 2): MatrixCell(1, 2, "-", (_PAGE_101,)),  # A0 + B1 → sin atribución
    (3, 5): MatrixCell(3, 5, "B*", (_PAGE_101,)),  # A2 + B4 → observación
}

_EXCEPTIONS = (
    MatrixException(
        note_id="obs-a2-b4",
        text="A2 + B4 = Culpable B, salvo que el A abra la puerta.",
        positions=((3, 5),),
        fact="door_opened_by",
        actor="A",
        liable_unless_exception="B",
        evidence_ids=(_PAGE_101,),
    ),
)


def _run(facts: tuple[ClaimFact, ...]) -> ClaimExecution:
    workflow = LangGraphClaimWorkflow(
        fact_extractor=_Extractor(ExtractedClaimFacts(("A", "B"), facts, InterviewPlan("ready"))),
        retriever=_Retriever(),
        evidence_repository=_Evidence(
            PageEvidence("manual:page:56", "a" * 64, 56, "texto", None, None, ())
        ),
        rules=(_MATRIX_RULE,),
        matrix_cells=_CELLS,
        matrix_exceptions=_EXCEPTIONS,
    )
    return asyncio.run(workflow.run(ClaimInput("Parte amistoso con el apartado 12 marcado.")))


def _base_facts(**boxes: str) -> tuple[ClaimFact, ...]:
    declared = {"daa_box_a": "A1", "daa_box_b": "B8", **boxes}
    return (
        ClaimFact("vehicle_count", "2", None, "dos vehículos"),
        ClaimFact("direct_collision", "true", None, "colisión directa"),
        ClaimFact("daa_section_12_only", "true", None, "sólo el apartado 12"),
        *(ClaimFact(name, value, None, f"casilla {value}") for name, value in declared.items()),
    )


def test_a_declared_daa_pair_resolves_the_claim_by_the_cide_table() -> None:
    result = _run(_base_facts()).result

    assert result.applicability == "applicable"
    assert result.convention == "CIDE"
    assert result.decision == "resolved"
    assert any(
        evaluation.rule_id == "cide-matrix-lookup" and evaluation.result == "matched"
        for evaluation in result.rules_evaluated
    )
    narrative = " ".join(block.text for block in result.blocks)
    assert "B" in narrative
    assert any(_PAGE_101 in block.evidence_ids for block in result.blocks)


def test_a_narrative_without_declared_boxes_never_resolves_by_the_table() -> None:
    """La matriz sigue protegida: sin casillas declaradas no se aplica."""
    facts = (
        ClaimFact("vehicle_count", "2", None, "dos vehículos"),
        ClaimFact("direct_collision", "true", None, "colisión directa"),
    )
    result = _run(facts).result

    assert result.decision != "resolved"
    assert all(
        evaluation.result != "matched"
        for evaluation in result.rules_evaluated
        if evaluation.rule_id == "cide-matrix-lookup"
    )


def test_a_dash_cell_does_not_resolve_and_says_the_table_attributes_nothing() -> None:
    result = _run(_base_facts(daa_box_a="A0", daa_box_b="B1")).result

    assert result.decision != "resolved"
    narrative = " ".join(block.text for block in result.blocks)
    assert "no atribuye" in narrative.lower()


def test_a_starred_cell_asks_for_its_observation_before_deciding() -> None:
    result = _run(_base_facts(daa_box_a="A2", daa_box_b="B4")).result

    assert result.decision == "conditional"
    assert result.conditions
    assert any("puerta" in condition.lower() for condition in result.conditions)


def test_a_starred_cell_resolves_when_the_observation_is_ruled_out() -> None:
    result = _run(_base_facts(daa_box_a="A2", daa_box_b="B4", door_opened_by="B")).result

    assert result.decision == "resolved"
    assert result.convention == "CIDE"


def test_a_starred_cell_withdraws_the_attribution_when_the_observation_holds() -> None:
    result = _run(_base_facts(daa_box_a="A2", daa_box_b="B4", door_opened_by="A")).result

    assert result.decision != "resolved"
    narrative = " ".join(block.text for block in result.blocks)
    assert "salvo que el A abra la puerta" in narrative
