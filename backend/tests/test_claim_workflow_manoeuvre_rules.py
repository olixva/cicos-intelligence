"""El flujo de siniestros resuelve con las normas subsidiarias recién conectadas.

A diferencia de `test_claim_workflow_matrix.py`, aquí se carga el artefacto
firmado real (`load_rules_artifacts`), no un `LoadedRule` construido a mano:
esto comprueba que el `applies_when` tal y como está escrito en
`data/rules/ruleset.v1.json` produce el resultado correcto a través del grafo
completo, no sólo en el evaluador aislado.
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path

from application.models.claim import ClaimExecution, ExtractedClaimFacts, InterviewPlan
from application.models.retrieval import Chunk
from application.ports.outbound.claim_fact_extractor import ClaimFactExtractor
from application.ports.outbound.evidence_reader import EvidenceReader
from application.ports.outbound.retriever import RetrievalRequest, Retriever
from domain.models.claim import ClaimFact, ClaimInput
from domain.models.evidence import PageEvidence
from infrastructure.adapters.outbound.claim_workflow.langgraph_workflow import (
    LangGraphClaimWorkflow,
)
from infrastructure.config.rules_artifacts import load_rules_artifacts

_REPO = Path(__file__).resolve().parents[2]
_DOCUMENT_HASH = "b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344"


@dataclass
class _Extractor(ClaimFactExtractor):
    facts: tuple[ClaimFact, ...]
    parties: tuple[str, ...] = ("A", "B")

    async def extract(self, claim: ClaimInput) -> ExtractedClaimFacts:
        return ExtractedClaimFacts(self.parties, self.facts, InterviewPlan("ready"))


class _Retriever(Retriever):
    async def retrieve(self, request: RetrievalRequest) -> tuple[Chunk, ...]:
        return (Chunk("criteria", "Normas subsidiarias ASCIDE.", ("manual:page:56",)),)


@dataclass
class _Evidence(EvidenceReader):
    page: PageEvidence

    def get(self, evidence_id: str) -> PageEvidence:
        return self.page


def _run(facts: tuple[ClaimFact, ...]) -> ClaimExecution:
    artifacts = load_rules_artifacts(
        _REPO / "data" / "rules",
        expected_document_hash=_DOCUMENT_HASH,
        evidence_roots=(_REPO / "data" / "extractions",),
    )
    workflow = LangGraphClaimWorkflow(
        fact_extractor=_Extractor(facts),
        retriever=_Retriever(),
        evidence_repository=_Evidence(
            PageEvidence("manual:page:56", "a" * 64, 56, "texto", None, None, ())
        ),
        rules=artifacts.rules,
        matrix_cells=artifacts.matrix_cells,
        matrix_exceptions=artifacts.matrix_exceptions,
    )
    return asyncio.run(workflow.run(ClaimInput("Relato de prueba.")))


def _base(**extra: str) -> tuple[ClaimFact, ...]:
    values = {"vehicle_count": "2", "direct_collision": "true", **extra}
    return tuple(ClaimFact(name, value, None, value) for name, value in values.items())


def test_parked_vehicle_resolves_to_the_colliding_vehicle() -> None:
    result = _run(
        _base(
            one_vehicle_parked="true", collision_with_parked_vehicle="true", colliding_vehicle="B"
        )
    ).result

    assert result.applicability == "applicable"
    assert result.convention == "ASCIDE"
    assert result.decision == "resolved"
    assert any(
        evaluation.rule_id == "ascide-b5-parked-vehicle" and evaluation.result == "matched"
        for evaluation in result.rules_evaluated
    )


def test_exit_from_parking_resolves_to_the_exiting_vehicle() -> None:
    result = _run(_base(exit_manoeuvre_by="A", exit_disputed_as_incorporation="false")).result

    assert result.decision == "resolved"
    assert result.convention == "ASCIDE"


def test_exit_from_parking_defers_when_disputed_as_incorporation() -> None:
    """El manual remite esta excepción a otro apartado no verificado."""
    result = _run(_base(exit_manoeuvre_by="A", exit_disputed_as_incorporation="true")).result

    assert result.decision != "resolved"


def test_reverse_vs_rear_impact_resolves_to_the_front_damage_vehicle() -> None:
    result = _run(_base(contradictory_versions="true", front_damage_vehicle="A")).result

    assert result.decision == "resolved"
    assert result.convention == "ASCIDE"


def test_door_opening_resolves_only_without_a_specified_action() -> None:
    result = _run(
        _base(door_involved="true", door_opening_specified="false", door_vehicle="B")
    ).result

    assert result.decision == "resolved"
    assert result.convention == "CIDE"


def test_door_opening_defers_when_the_action_is_specified() -> None:
    result = _run(
        _base(door_involved="true", door_opening_specified="true", door_vehicle="B")
    ).result

    assert result.decision != "resolved"
