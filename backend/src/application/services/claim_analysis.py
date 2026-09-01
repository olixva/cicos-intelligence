"""Pure construction of safe provisional claim decisions."""

from domain.models.claim import ClaimEvidenceBlock, ClaimFact
from domain.models.decision import ClaimAnalysis
from domain.rules.applicability import ApplicabilityAssessment


def build_applicability_analysis(
    *,
    parties: tuple[str, ...],
    facts: tuple[ClaimFact, ...],
    assessment: ApplicabilityAssessment,
) -> ClaimAnalysis:
    """Return a convention-scoped result without attributing liability prematurely."""

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
    return ClaimAnalysis(
        applicability="applicable",
        convention=None,
        decision="undetermined",
        party_ids=parties,
        facts=facts,
        contradictions=(),
        conditions=(),
        missing_information=("Determinar el convenio y las circunstancias aplicables.",),
        blocks=(),
    )
