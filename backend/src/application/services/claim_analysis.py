"""Pure construction of safe provisional claim decisions."""

from typing import Literal

from domain.models.claim import ClaimEvidenceBlock, ClaimFact
from domain.models.decision import ClaimAnalysis
from domain.models.rule_evaluation import RuleEvaluation
from domain.rules.applicability import ApplicabilityAssessment


def build_applicability_analysis(
    *,
    parties: tuple[str, ...],
    facts: tuple[ClaimFact, ...],
    assessment: ApplicabilityAssessment,
    matched_manoeuvre_rules: tuple[RuleEvaluation, ...] = (),
    manoeuvre_convention: Literal["CIDE", "ASCIDE"] | None = None,
) -> ClaimAnalysis:
    """Return a convention-scoped result without attributing liability prematurely.

    ``matched_manoeuvre_rules`` holds only ``"matched"`` evaluations of manoeuvre
    rules, e.g. lane-change or parked-vehicle. A single unambiguous match resolves
    the claim; zero or several conflicting matches stay ``undetermined`` rather
    than guessing between them.

    ``manoeuvre_convention`` is the convention that matched rule declares in the
    signed artifact. It is **not** inferred from the rule's kind: ``manoeuvre``
    covers both the ASCIDE subsidiary norms and the CIDE door-opening criterion.
    When the artifact does not state one, the claim still resolves but names no
    convention instead of assuming it.
    """

    if assessment.status == "not_applicable":
        text = "No procede aplicar el Convenio con los hechos confirmados. " + " ".join(
            assessment.reasons
        )
        return ClaimAnalysis(
            applicability="not_applicable",
            convention=None,
            decision="not_assessed",
            party_ids=parties,
            facts=facts,
            contradictions=(),
            conditions=(),
            missing_information=(),
            blocks=(ClaimEvidenceBlock(text, assessment.evidence_ids),),
        )
    if assessment.status == "undetermined":
        return ClaimAnalysis(
            applicability="undetermined",
            convention=None,
            decision="conditional",
            party_ids=parties,
            facts=facts,
            contradictions=(),
            conditions=assessment.missing_information,
            missing_information=assessment.missing_information,
            blocks=(),
        )
    if len(matched_manoeuvre_rules) == 1:
        rule = matched_manoeuvre_rules[0]
        return ClaimAnalysis(
            applicability="applicable",
            convention=manoeuvre_convention,
            decision="resolved",
            party_ids=parties,
            facts=facts,
            contradictions=(),
            conditions=(),
            missing_information=(),
            blocks=(ClaimEvidenceBlock(rule.rationale, rule.evidence_ids),),
            rules_evaluated=matched_manoeuvre_rules,
        )
    missing_information = _personalized_missing_information(facts)
    return ClaimAnalysis(
        applicability="applicable",
        convention=None,
        decision="undetermined",
        party_ids=parties,
        facts=facts,
        contradictions=(),
        conditions=(),
        missing_information=missing_information,
        blocks=(),
    )


def _personalized_missing_information(facts: tuple[ClaimFact, ...]) -> tuple[str, ...]:
    """Ask about an observable accident fact, never about internal DAA fields.

    A fully described claim can remain ``undetermined`` when no reviewed rule
    matches it; that is not a reason to interrupt the conversation asking for
    the CIDE form's internal boxes. Only a claim with no manoeuvre narrative
    gets a follow-up question, phrased in terms a person can answer.
    """
    values = {fact.name: fact.value for fact in facts if fact.value is not None}
    core = {
        "vehicle_count",
        "direct_collision",
        "third_vehicle_identified",
        "chain_collision",
    }
    if any(name not in core for name in values):
        return ()
    return (
        "¿Qué maniobra realizaba cada vehículo justo antes del impacto? "
        "Si existen versiones de A y B, describe ambas.",
    )
