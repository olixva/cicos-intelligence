"""The claim envelope must carry the reasoning, not just three enum values.

The API used to expose only applicability, convention and decision, so the
interface could say no more than "Aplicabilidad: undetermined. Decisión:
conditional." — three words of jargon with nothing behind them. The domain
already computes attributed facts, contradictions, conditions, missing
information and cited explanation blocks; the envelope has to deliver them.
"""

from application.models.claim import ClaimExecution
from domain.models.claim import ClaimContradiction, ClaimEvidenceBlock, ClaimFact
from domain.models.decision import ClaimAnalysis
from infrastructure.adapters.inbound.api.schemas.envelope import EnvelopeResponse

_EVIDENCE = "sha256:" + "b" * 64 + ":page:56"


def _analysis() -> ClaimAnalysis:
    said_by_a = ClaimFact("vehicle_count", "2", "A", "Intervinieron dos vehículos.")
    said_by_b = ClaimFact("vehicle_count", "3", "B", "Había un tercer coche implicado.")
    return ClaimAnalysis(
        applicability="undetermined",
        convention=None,
        decision="conditional",
        party_ids=("A", "B"),
        facts=(said_by_a, said_by_b),
        contradictions=(ClaimContradiction("vehicle_count", (said_by_a, said_by_b)),),
        conditions=("Confirmar cuántos vehículos intervinieron.",),
        missing_information=("Número de vehículos implicados.",),
        blocks=(ClaimEvidenceBlock("Los Convenios exigen dos vehículos.", (_EVIDENCE,)),),
    )


def _envelope() -> EnvelopeResponse:
    return EnvelopeResponse.from_claim(
        request_id="req-1",
        execution=ClaimExecution(result=_analysis(), context=(), trace_id="t-1"),
    )


def test_claim_envelope_exposes_the_explanation_blocks() -> None:
    result = _envelope().result
    assert result.kind == "claim"
    assert result.blocks
    assert result.blocks[0]["text"] == "Los Convenios exigen dos vehículos."
    assert result.blocks[0]["evidence_ids"] == (_EVIDENCE,)


def test_claim_envelope_exposes_conditions_and_missing_information() -> None:
    """A conditional decision is only meaningful next to its conditions."""
    result = _envelope().result
    assert result.conditions == ("Confirmar cuántos vehículos intervinieron.",)
    assert result.missing_information == ("Número de vehículos implicados.",)


def test_claim_envelope_keeps_facts_attributed_to_who_said_them() -> None:
    result = _envelope().result
    assert result.party_ids == ("A", "B")
    by_party = {(fact["asserted_by"], fact["value"]) for fact in result.facts}
    assert by_party == {("A", "2"), ("B", "3")}


def test_claim_envelope_keeps_contradictions_unresolved_and_visible() -> None:
    """The system must show the disagreement, never silently pick a side."""
    result = _envelope().result
    assert len(result.contradictions) == 1
    contradiction = result.contradictions[0]
    assert contradiction["fact_name"] == "vehicle_count"
    assert len(contradiction["statements"]) == 2


def test_claim_envelope_never_leaks_local_asset_paths() -> None:
    """Whatever we add, image_path and filesystem roots stay out of the API."""
    payload = _envelope().model_dump_json()
    assert "image_path" not in payload
    assert "data/extractions" not in payload


# ---------------------------------------------------------------------------
# Auto mode must not degrade the answer. It is the default mode, so a claim
# routed through the classifier has to carry exactly what the explicit claim
# endpoint carries.
# ---------------------------------------------------------------------------

from application.models.query import QueryInput  # noqa: E402
from domain.models.routing import RouteClassification, RouteExecution  # noqa: E402


def _auto_envelope() -> EnvelopeResponse:
    return EnvelopeResponse.from_route_execution(
        request_id="req-2",
        execution=RouteExecution(
            query=QueryInput("relato", "es"),
            classification=RouteClassification("claim"),
            dispatch=ClaimExecution(result=_analysis(), context=(), trace_id="t-1"),
            trace_id="t-route",
        ),
    )


def test_auto_routed_claim_carries_the_same_content_as_the_explicit_one() -> None:
    explicit = _envelope().result
    auto = _auto_envelope().result
    assert auto.kind == "claim"
    assert explicit.kind == "claim"
    for field in (
        "applicability",
        "convention",
        "decision",
        "party_ids",
        "facts",
        "contradictions",
        "conditions",
        "missing_information",
        "blocks",
    ):
        assert getattr(auto, field) == getattr(explicit, field), field


def test_auto_routed_claim_keeps_the_workflow_trace_url() -> None:
    """The route wrapper must not drop the URL the workflow resolved."""
    execution = ClaimExecution(
        result=_analysis(), context=(), trace_id="t-1", trace_url="https://lf/x/traces/t-1"
    )
    envelope = EnvelopeResponse.from_route_execution(
        request_id="req-3",
        execution=RouteExecution(
            query=QueryInput("relato", "es"),
            classification=RouteClassification("claim"),
            dispatch=execution,
            trace_id="t-route",
        ),
    )
    assert envelope.result.trace_url == "https://lf/x/traces/t-1"


def test_claim_envelope_exposes_every_rule_that_ran() -> None:
    """The interface has to be able to show what was checked, not just the verdict."""
    from domain.models.rule_evaluation import RuleEvaluation

    analysis = _analysis()
    with_rules = ClaimAnalysis(
        applicability=analysis.applicability,
        convention=analysis.convention,
        decision=analysis.decision,
        party_ids=analysis.party_ids,
        facts=analysis.facts,
        contradictions=analysis.contradictions,
        conditions=analysis.conditions,
        missing_information=analysis.missing_information,
        blocks=analysis.blocks,
        rules_evaluated=(
            RuleEvaluation(
                rule_id="chain-collision-excludes-convention",
                inputs=(("chain_collision", "true"),),
                result="matched",
                evidence_ids=(_EVIDENCE,),
                rationale="La colisión en cadena no se tramita por Convenio.",
            ),
            RuleEvaluation(
                rule_id="ascide-b10-lane-change",
                inputs=(),
                result="insufficient_data",
                evidence_ids=(),
                rationale="No se evalúa automáticamente.",
            ),
        ),
    )
    result = EnvelopeResponse.from_claim(
        request_id="req-9",
        execution=ClaimExecution(result=with_rules, context=(), trace_id="t"),
    ).result
    assert len(result.rules_evaluated) == 2
    matched = result.rules_evaluated[0]
    assert matched["rule_id"] == "chain-collision-excludes-convention"
    assert matched["result"] == "matched"
    assert matched["evidence_ids"] == (_EVIDENCE,)
    # Una regla no comprobable se reporta, pero sin evidencia que la respalde.
    assert result.rules_evaluated[1]["result"] == "insufficient_data"
    assert result.rules_evaluated[1]["evidence_ids"] == ()
