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
    return ClaimAnalysis(
        applicability="applicable",
        convention=None,
        decision="undetermined",
        party_ids=parties,
        facts=facts,
        contradictions=(),
        conditions=(),
        missing_information=_MISSING_TO_ATTRIBUTE_FAULT,
        blocks=(),
    )


#: Qué hace falta para pasar de "el Convenio se aplica" a "quién responde".
#: El texto anterior —«Determinar el convenio y las circunstancias
#: aplicables»— era circular: decía que el Convenio es aplicable y acto
#: seguido pedía determinar el convenio, sin indicar qué dato falta. Estas
#: tres entradas nombran los datos concretos que el manual exige.
_MISSING_TO_ATTRIBUTE_FAULT: tuple[str, ...] = (
    "Las casillas del apartado 12 de la D.A.A. (A0–A17) declaradas por ambos "
    "vehículos: sin ellas no puede aplicarse la tabla de culpabilidad CIDE.",
    "O bien los hechos concretos de la maniobra que activen una norma subsidiaria "
    "ASCIDE: cambio de carril reconocido por ambos, vehículo aparcado, salida de "
    "estacionamiento, marcha atrás, rotonda o semáforo en ámbar.",
    "Si existe D.A.A. conjunta firmada por ambos conductores (vía CIDE) o "
    "declaración informatizada (vía ASCIDE), para saber por qué convenio se tramita.",
)
