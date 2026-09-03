"""Servicio de analisis de siniestros y los cinco casos del enunciado."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from application.models.claim import ClaimExecution, ExtractedClaimFacts
from application.models.retrieval import Chunk
from application.ports.outbound.claim_fact_extractor import ClaimFactExtractor
from application.ports.outbound.evidence_reader import EvidenceReader
from application.ports.outbound.retriever import RetrievalRequest, Retriever
from domain.models.claim import ClaimFact, ClaimInput
from domain.models.decision import ClaimAnalysis
from domain.models.evidence import PageEvidence
from domain.rules.ruleset import evaluate_ruleset
from infrastructure.config.rules_artifacts import load_rules_artifacts

# --------------------------------------------------------------------------
# Claim analysis uses applicability as a safe gate before responsibility rules.
# --------------------------------------------------------------------------


def test_unknown_applicability_produces_a_conditional_result_with_questions() -> None:
    from application.services.claim_analysis import build_applicability_analysis
    from domain.rules.applicability import ApplicabilityAssessment

    result = build_applicability_analysis(
        parties=("A", "B"),
        facts=(),
        assessment=ApplicabilityAssessment(
            "undetermined", (), ("Confirmar cuántos vehículos intervinieron.",), ("manual:56",)
        ),
    )

    assert result.decision == "conditional"
    assert result.conditions == ("Confirmar cuántos vehículos intervinieron.",)


def test_not_applicable_does_not_attribute_responsibility() -> None:
    from application.services.claim_analysis import build_applicability_analysis
    from domain.rules.applicability import ApplicabilityAssessment

    result = build_applicability_analysis(
        parties=("A", "B"),
        facts=(),
        assessment=ApplicabilityAssessment(
            "not_applicable", ("Hay tres vehículos.",), (), ("manual:56",)
        ),
    )

    assert result.decision == "not_assessed"
    assert result.blocks[0].evidence_ids == ("manual:56",)


def test_a_single_matched_manoeuvre_rule_resolves_the_claim() -> None:
    from application.services.claim_analysis import build_applicability_analysis
    from domain.models.rule_evaluation import RuleEvaluation
    from domain.rules.applicability import ApplicabilityAssessment

    matched = RuleEvaluation(
        rule_id="ascide-b10-lane-change",
        inputs=(("lane_change_acknowledged_by_both", "true"), ("contradictory_versions", "true")),
        result="matched",
        evidence_ids=("manual:75",),
        rationale="Culpable quien cambia de carril.",
    )
    result = build_applicability_analysis(
        parties=("A", "B"),
        facts=(),
        assessment=ApplicabilityAssessment("applicable", (), (), ("manual:56",)),
        matched_manoeuvre_rules=(matched,),
        manoeuvre_convention="ASCIDE",
    )

    assert result.decision == "resolved"
    assert result.convention == "ASCIDE"
    assert result.blocks[0].text == matched.rationale
    assert result.blocks[0].evidence_ids == matched.evidence_ids
    assert result.rules_evaluated == (matched,)


def test_convention_comes_from_the_rule_not_from_its_kind() -> None:
    """`manoeuvre` covers ASCIDE subsidiary norms *and* the CIDE door-opening rule,
    so the convention must be read from the artifact, never assumed from the kind."""
    from application.services.claim_analysis import build_applicability_analysis
    from domain.models.rule_evaluation import RuleEvaluation
    from domain.rules.applicability import ApplicabilityAssessment

    matched = RuleEvaluation(
        rule_id="cide-door-opening",
        inputs=(("door_opening", "true"),),
        result="matched",
        evidence_ids=("manual:91",),
        rationale="Deudora la aseguradora del vehículo que abre la puerta.",
    )
    result = build_applicability_analysis(
        parties=("A", "B"),
        facts=(),
        assessment=ApplicabilityAssessment("applicable", (), (), ("manual:56",)),
        matched_manoeuvre_rules=(matched,),
        manoeuvre_convention="CIDE",
    )

    assert result.decision == "resolved"
    assert result.convention == "CIDE"


def test_a_matched_rule_without_a_declared_convention_names_none() -> None:
    """Resolving is fine; inventing which convention applies is not."""
    from application.services.claim_analysis import build_applicability_analysis
    from domain.models.rule_evaluation import RuleEvaluation
    from domain.rules.applicability import ApplicabilityAssessment

    matched = RuleEvaluation(
        rule_id="unlabelled-rule",
        inputs=(),
        result="matched",
        evidence_ids=("manual:75",),
        rationale="Regla sin convenio declarado.",
    )
    result = build_applicability_analysis(
        parties=("A", "B"),
        facts=(),
        assessment=ApplicabilityAssessment("applicable", (), (), ("manual:56",)),
        matched_manoeuvre_rules=(matched,),
    )

    assert result.decision == "resolved"
    assert result.convention is None


def test_shipped_ruleset_declares_the_convention_of_every_manoeuvre_rule() -> None:
    """Regression: a manoeuvre rule with no convention would resolve without naming one."""
    from pathlib import Path

    from infrastructure.config.rules_artifacts import load_rules_artifacts

    repo = Path(__file__).resolve().parents[2]
    artifacts = load_rules_artifacts(
        repo / "data" / "rules",
        expected_document_hash="b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344",
        evidence_roots=(repo / "data" / "extractions",),
    )
    manoeuvre = [rule for rule in artifacts.rules if rule.kind == "manoeuvre"]
    assert manoeuvre, "the shipped ruleset must keep its manoeuvre rules"
    assert all(rule.convention in ("CIDE", "ASCIDE") for rule in manoeuvre)
    by_id = {rule.rule_id: rule.convention for rule in artifacts.rules}
    assert by_id["ascide-b10-lane-change"] == "ASCIDE"
    assert by_id["cide-door-opening"] == "CIDE"


def test_zero_matched_manoeuvre_rules_stay_undetermined() -> None:
    from application.services.claim_analysis import build_applicability_analysis
    from domain.rules.applicability import ApplicabilityAssessment

    result = build_applicability_analysis(
        parties=("A", "B"),
        facts=(),
        assessment=ApplicabilityAssessment("applicable", (), (), ("manual:56",)),
    )

    assert result.decision == "undetermined"
    assert result.convention is None


def test_conflicting_matched_manoeuvre_rules_stay_undetermined_instead_of_guessing() -> None:
    from application.services.claim_analysis import build_applicability_analysis
    from domain.models.rule_evaluation import RuleEvaluation
    from domain.rules.applicability import ApplicabilityAssessment

    first = RuleEvaluation(
        rule_id="ascide-b9-reverse-vs-rear-impact",
        inputs=(),
        result="matched",
        evidence_ids=("manual:75",),
        rationale="Responsable quien presenta daños en la parte delantera.",
    )
    second = RuleEvaluation(
        rule_id="ascide-b10-lane-change",
        inputs=(),
        result="matched",
        evidence_ids=("manual:75",),
        rationale="Culpable quien cambia de carril.",
    )
    result = build_applicability_analysis(
        parties=("A", "B"),
        facts=(),
        assessment=ApplicabilityAssessment("applicable", (), (), ("manual:56",)),
        matched_manoeuvre_rules=(first, second),
    )

    assert result.decision == "undetermined"
    assert result.convention is None


# --------------------------------------------------------------------------
# Bounded honesty tests for the documented claim scenarios.
#
# These tests do not assert fabricated outcomes. Until the CIDE matrix and
# the ruleset are transcribed by humans (T5), every case that would
# require the matrix or a rule must surface an explicit ``undetermined``
# result with the reason documented in ``missing_information`` or
# ``conditions``. The tests below lock in that contract so a future
# change cannot silently introduce a placeholder or hallucinated
# decision.
#
# The tests rely on the workflow's own fact vocabulary:
# - ``vehicle_count``: integer string ("2", "3", ...).
# - ``direct_collision``: "true" / "false".
# - ``third_vehicle_identified``: "true" / "false".
# - ``chain_collision``: "true" / "false".
# - ``maneuver_a`` / ``maneuver_b``: any string for now.
# --------------------------------------------------------------------------


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
    facts = (ClaimFact("vehicle_count", "0", None, "no intervienen vehículos"),)
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
    assert (
        "matriz" not in block_texts
        or "no evaluada" in block_texts
        or "indeterminada" in block_texts
    )
    assert execution.context, "context must carry the evidence actually delivered to the LLM"


# --------------------------------------------------------------------------
# The five accidents from the interview brief, as an executable contract.
#
# Four of the five fall outside the CIDE/ASCIDE conventions. The specification
# is explicit that abstaining is the correct answer there — "no se exige
# inventar una conclusión definitiva" — so these tests assert the reasoning the
# system must show, not just the enum it lands on.
# --------------------------------------------------------------------------


_RULES = load_rules_artifacts(Path(__file__).resolve().parents[2] / "data" / "rules").rules


def _by_id(facts: dict[str, str]) -> dict[str, str]:
    """Run the shipped ruleset and index the outcome of every rule."""
    return {ev.rule_id: ev.result for ev in evaluate_ruleset(_RULES, facts)}


def test_accident_1_rear_end_at_a_red_light_stays_inside_the_convention() -> None:
    """Two vehicles, direct collision: nothing excludes the convention."""
    results = _by_id({"vehicle_count": "2", "direct_collision": "true", "chain_collision": "false"})
    assert results["cide-requires-two-vehicles"] == "not_matched"
    assert results["cide-requires-direct-collision"] == "not_matched"
    assert results["chain-collision-excludes-convention"] == "not_matched"


def test_accident_2_five_car_pileup_is_excluded_twice_over() -> None:
    """More than two vehicles AND a chain collision: two independent exclusions."""
    results = _by_id({"vehicle_count": "5", "direct_collision": "true", "chain_collision": "true"})
    assert results["cide-requires-two-vehicles"] == "matched"
    assert results["chain-collision-excludes-convention"] == "matched"


def test_accident_3_hit_and_run_on_a_parked_car_has_no_second_party() -> None:
    """Only one identified vehicle, so the two-vehicle requirement fails."""
    results = _by_id({"vehicle_count": "1", "direct_collision": "true"})
    assert results["cide-requires-two-vehicles"] == "matched"


def test_accident_4_lane_change_is_not_decided_automatically_yet() -> None:
    """The ASCIDE b.10 norm is documented but not machine-checkable today.

    It must report insufficient_data rather than be presented as applied.
    """
    results = _by_id({"vehicle_count": "2", "direct_collision": "true", "lane_change": "true"})
    assert results["ascide-b10-lane-change"] == "insufficient_data"
    assert results["cide-requires-two-vehicles"] == "not_matched"


def test_accident_5_alcohol_does_not_exclude_the_convention() -> None:
    """Page 9 says so outright; the rule exists to stop a wrong exclusion."""
    results = _by_id(
        {
            "vehicle_count": "2",
            "direct_collision": "true",
            "driver_under_influence": "true",
        }
    )
    assert results["alcohol-does-not-exclude-convention"] == "matched"
    assert results["cide-requires-two-vehicles"] == "not_matched"


def test_no_rule_is_ever_matched_without_the_evidence_that_supports_it() -> None:
    evaluations = evaluate_ruleset(
        _RULES, {"vehicle_count": "5", "direct_collision": "true", "chain_collision": "true"}
    )
    for evaluation in evaluations:
        if evaluation.result == "matched":
            assert evaluation.evidence_ids, evaluation.rule_id


def test_every_rule_reports_something_so_the_interface_can_show_its_work() -> None:
    evaluations = evaluate_ruleset(_RULES, {"vehicle_count": "2"})
    assert len(evaluations) == len(_RULES)
    assert {e.rule_id for e in evaluations} == {r.rule_id for r in _RULES}


# --------------------------------------------------------------------------
# The claim input port delegates unchanged user facts to its workflow.
# --------------------------------------------------------------------------


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
