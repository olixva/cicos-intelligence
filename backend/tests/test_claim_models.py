"""Safety invariants for attributable claim facts and convention decisions."""

import pytest


def test_contradictory_statements_keep_their_respective_attribution() -> None:
    from domain.models.claim import ClaimContradiction, ClaimFact

    first = ClaimFact("traffic_light", "verde", "A", "A declara que tenía verde")
    second = ClaimFact("traffic_light", "rojo", "B", "B declara que A tenía rojo")

    contradiction = ClaimContradiction("traffic_light", (first, second))

    assert contradiction.statements == (first, second)


def test_conditional_claim_requires_visible_conditions() -> None:
    from domain.models.decision import ClaimAnalysis, InvalidDecisionError

    with pytest.raises(InvalidDecisionError, match="conditional"):
        ClaimAnalysis(
            applicability="undetermined",
            convention=None,
            decision="conditional",
            party_ids=("A", "B"),
            facts=(),
            contradictions=(),
            conditions=(),
            missing_information=("Confirmar las circunstancias.",),
            blocks=(),
        )


def test_inapplicable_convention_cannot_return_a_resolved_decision() -> None:
    from domain.models.decision import ClaimAnalysis, InvalidDecisionError

    with pytest.raises(InvalidDecisionError, match="inapplicable"):
        ClaimAnalysis(
            applicability="not_applicable",
            convention=None,
            decision="resolved",
            party_ids=("A", "B"),
            facts=(),
            contradictions=(),
            conditions=(),
            missing_information=(),
            blocks=(),
        )
