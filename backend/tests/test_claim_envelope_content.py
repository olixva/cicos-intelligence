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
