"""Bounded honesty tests for the documented claim scenarios.

These tests do not assert fabricated outcomes. Until the CIDE matrix and
the ruleset are transcribed by humans (T5), every case that would
require the matrix or a rule must surface an explicit ``undetermined``
result with the reason documented in ``missing_information`` or
``conditions``. The tests below lock in that contract so a future
change cannot silently introduce a placeholder or hallucinated
decision.

The tests rely on the workflow's own fact vocabulary:
- ``vehicle_count``: integer string ("2", "3", ...).
- ``direct_collision``: "true" / "false".
- ``third_vehicle_identified``: "true" / "false".
- ``chain_collision``: "true" / "false".
- ``maneuver_a`` / ``maneuver_b``: any string for now.
"""

from __future__ import annotations

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
        return (Chunk("criteria", "El Convenio exige dos vehículos.", ("manual:page:56",)),)


@dataclass
class _Evidence(EvidenceReader):
    page: PageEvidence

    def get(self, evidence_id: str) -> PageEvidence:
        assert evidence_id == self.page.evidence_id
        return self.page


def _build_workflow(facts: tuple[ClaimFact, ...], speakers: tuple[str, ...] = ("A", "B")):
    from infrastructure.adapters.outbound.claim_workflow.langgraph_workflow import (
        LangGraphClaimWorkflow,
    )

    return LangGraphClaimWorkflow(
        fact_extractor=_Extractor(ExtractedClaimFacts(speakers, facts)),
        retriever=_Retriever(),
        evidence_repository=_Evidence(
            PageEvidence("manual:page:56", "a" * 64, 56, "texto", None, None, ())
        ),
    )


def test_parked_third_vehicle_stays_undetermined_without_ruleset() -> None:
    """Two moving vehicles + one parked (non-intervening) third: applicability
    is satisfied but the matrix outcome cannot be decided until the
    ruleset is loaded, so the decision must remain undetermined with the
    reason visible.
    """
    facts = (
        ClaimFact("vehicle_count", "2", None, "A y B circulando"),
        ClaimFact(
            "third_vehicle_identified",
            "false",
            None,
            "hay un tercero estacionado que no interviene",
        ),
        ClaimFact("direct_collision", "true", None, "A y B chocan frontalmente"),
        ClaimFact("maneuver_a", None, None, "no declarada"),
        ClaimFact("maneuver_b", None, None, "no declarada"),
    )
    execution: ClaimExecution = asyncio.run(
        _build_workflow(facts).run(ClaimInput("A y B chocan; un tercero estaba estacionado."))
    )

    assert execution.result.applicability == "applicable"
    assert execution.result.decision == "undetermined"
    joined = " ".join(execution.result.missing_information)
    assert joined, "the workflow must explain why the decision is undetermined"
    assert joined != "", "missing_information must not be empty for undetermined decisions"


def test_unknown_maneuver_returns_undetermined_with_concrete_missing_fields() -> None:
    """When neither A nor B states their manoeuvre, the workflow must not
    guess; it has to ask and leave the decision undetermined.

    Until the ruleset is loaded (T5), the workflow surfaces a generic
    missing_information block rather than fabricating a decision. This
    test locks the contract: no decision, non-empty missing_information,
    and no fact is silently promoted.
    """
    facts = (
        ClaimFact("vehicle_count", "2", None, "dos coches"),
        ClaimFact("direct_collision", "true", None, "chocan"),
        ClaimFact("maneuver_a", None, None, "no declarada"),
        ClaimFact("maneuver_b", None, None, "no declarada"),
    )
    execution: ClaimExecution = asyncio.run(
        _build_workflow(facts).run(ClaimInput("Dos coches chocan."))
    )

    assert execution.result.applicability == "applicable"
    assert execution.result.decision == "undetermined"
    assert execution.result.missing_information, (
        "missing_information must be non-empty so the caller can request clarification"
    )
    promoted_facts = [fact.name for fact in execution.result.facts if fact.value is not None]
    assert "maneuver_a" not in promoted_facts
    assert "maneuver_b" not in promoted_facts


def test_contradictory_versions_preserve_attributions_without_deciding() -> None:
    """A and B disagree on who ran the red light. The workflow must keep
    both statements, never silently pick one, and leave the decision
    undetermined until the matrix can resolve it.
    """
    facts = (
        ClaimFact("vehicle_count", "2", None, "A y B"),
        ClaimFact("direct_collision", "true", None, "chocan en cruce"),
        ClaimFact(
            "red_light",
            "A estaba en verde",
            "A",
            "A declara que él tenía verde",
        ),
        ClaimFact(
            "red_light",
            "A estaba en rojo",
            "B",
            "B declara que A se saltó el rojo",
        ),
    )
    execution: ClaimExecution = asyncio.run(
        _build_workflow(facts).run(ClaimInput("A dice verde, B dice rojo."))
    )

    assert execution.result.applicability == "applicable"
    assert execution.result.decision == "undetermined"
    contradiction_facts = {c.fact_name for c in execution.result.contradictions}
    assert "red_light" in contradiction_facts
    red_contradiction = next(
        c for c in execution.result.contradictions if c.fact_name == "red_light"
    )
    speakers = {fact.asserted_by for fact in red_contradiction.statements}
    assert speakers == {"A", "B"}


def test_outside_convention_scope_is_marked_not_applicable() -> None:
    """A pedestrian-only accident without a vehicle-to-vehicle collision is
    outside CIDE/ASCIDE/CICOS. The applicability result must reflect that
    without resolving a decision, and the explanation must reach the
    caller via the result blocks.
    """
    facts = (
        ClaimFact("vehicle_count", "0", None, "no intervienen vehículos"),
    )
    execution: ClaimExecution = asyncio.run(
        _build_workflow(facts).run(ClaimInput("Un peatón fue atropellado por un turismo solo."))
    )

    assert execution.result.applicability == "not_applicable"
    assert execution.result.decision == "not_assessed"
    assert execution.result.blocks, (
        "the workflow must surface why the case is outside convention via blocks"
    )
    joined = " ".join((block.text or "") for block in execution.result.blocks).lower()
    assert "convenio" in joined or "vehículo" in joined, (
        "at least one block must explain the convention scope decision"
    )


def test_decision_undetermined_does_not_invoke_unevaluated_rules() -> None:
    """When the matrix is not loaded, the workflow must not emit blocks
    that pretend to have run the matrix; the result must surface the
    absence explicitly. This contract blocks future regressions that
    would attach placeholder rule traces.
    """
    facts = (
        ClaimFact("vehicle_count", "2", None, "A y B"),
        ClaimFact("direct_collision", "true", None, "chocan"),
        ClaimFact("maneuver_a", "cedió el paso", "A", "A declara"),
        ClaimFact("maneuver_b", "no cedió el paso", "B", "B declara"),
    )
    execution: ClaimExecution = asyncio.run(
        _build_workflow(facts).run(ClaimInput("Maniobra contradictoria."))
    )

    assert execution.result.decision in ("undetermined", "conditional")
    block_texts = " ".join((block.text or "") for block in execution.result.blocks).lower()
    assert "matriz" not in block_texts or "no evaluada" in block_texts or "indeterminada" in block_texts
    assert execution.context, "context must carry the evidence actually delivered to the LLM"
