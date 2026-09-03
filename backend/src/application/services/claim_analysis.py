"""Pure construction of safe provisional claim decisions."""

from typing import Literal

from domain.models.claim import ClaimEvidenceBlock, ClaimFact
from domain.models.decision import ClaimAnalysis
from domain.models.rule_evaluation import RuleEvaluation
from domain.rules.applicability import ApplicabilityAssessment
from domain.rules.cide_matrix import MatrixDecision


def build_applicability_analysis(
    *,
    parties: tuple[str, ...],
    facts: tuple[ClaimFact, ...],
    assessment: ApplicabilityAssessment,
    matched_manoeuvre_rules: tuple[RuleEvaluation, ...] = (),
    manoeuvre_convention: Literal["CIDE", "ASCIDE"] | None = None,
    matrix_decision: MatrixDecision | None = None,
    matrix_convention: Literal["CIDE", "ASCIDE"] | None = None,
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

    ``matrix_decision`` is only consulted when no manoeuvre rule already
    resolved the claim: a D.A.A. pair and a recognised manoeuvre should not
    coexist in the same narrative, and if they somehow do, guessing which one
    wins would be exactly the invented conclusion this function exists to
    avoid.
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
    if matrix_decision is not None:
        resolved = _from_matrix_decision(
            matrix_decision, parties=parties, facts=facts, convention=matrix_convention
        )
        if resolved is not None:
            return resolved
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


def _from_matrix_decision(
    decision: MatrixDecision,
    *,
    parties: tuple[str, ...],
    facts: tuple[ClaimFact, ...],
    convention: Literal["CIDE", "ASCIDE"] | None,
) -> ClaimAnalysis | None:
    """Turn what the CIDE table supports into a claim result, or defer.

    Returns ``None`` for ``"undetermined"`` (no D.A.A. pair declared): the
    caller falls back to asking a manoeuvre question instead. The other four
    statuses are the table's own possible answers and each maps to exactly
    one outcome — none of them a guess.
    """
    if decision.status == "attributes":
        text = (
            f"La tabla de culpabilidad CIDE atribuye la responsabilidad a {decision.liable_party}."
        )
        return ClaimAnalysis(
            applicability="applicable",
            convention=convention,
            decision="resolved",
            party_ids=parties,
            facts=facts,
            contradictions=(),
            conditions=(),
            missing_information=(),
            blocks=(ClaimEvidenceBlock(text, decision.evidence_ids),),
            # El invariante de dominio exige que un "resolved" cite al menos una
            # regla que casó; la propia consulta a la tabla es esa regla.
            rules_evaluated=(
                RuleEvaluation(
                    rule_id="cide-matrix-lookup",
                    inputs=(),
                    result="matched",
                    evidence_ids=decision.evidence_ids,
                    rationale=text,
                ),
            ),
        )
    if decision.status == "no_attribution":
        text = (
            "La tabla de culpabilidad CIDE no atribuye responsabilidad para esta "
            "combinación de casillas."
        )
        return ClaimAnalysis(
            applicability="applicable",
            convention=None,
            decision="undetermined",
            party_ids=parties,
            facts=facts,
            contradictions=(),
            conditions=(),
            missing_information=(),
            blocks=(ClaimEvidenceBlock(text, decision.evidence_ids),),
        )
    if decision.status == "needs_exception_fact":
        assert decision.exception_text is not None
        return ClaimAnalysis(
            applicability="applicable",
            convention=None,
            decision="conditional",
            party_ids=parties,
            facts=facts,
            contradictions=(),
            conditions=(decision.exception_text,),
            missing_information=(decision.exception_text,),
            blocks=(),
        )
    if decision.status == "exception_applies":
        assert decision.exception_text is not None
        return ClaimAnalysis(
            applicability="applicable",
            convention=None,
            decision="undetermined",
            party_ids=parties,
            facts=facts,
            contradictions=(),
            conditions=(),
            missing_information=(),
            blocks=(ClaimEvidenceBlock(decision.exception_text, decision.evidence_ids),),
        )
    return None


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
