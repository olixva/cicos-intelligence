"""Claim analysis uses applicability as a safe gate before responsibility rules."""


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
