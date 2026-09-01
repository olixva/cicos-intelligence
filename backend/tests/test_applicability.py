"""Applicability guards are evidence-bound and never infer missing prerequisites."""


def test_more_than_two_vehicles_is_not_applicable() -> None:
    from domain.rules.applicability import ApplicabilityFacts, assess_applicability

    result = assess_applicability(ApplicabilityFacts(3, True), evidence_ids=("manual:page:56",))

    assert result.status == "not_applicable"
    assert result.evidence_ids == ("manual:page:56",)


def test_unknown_prerequisite_stays_undetermined() -> None:
    from domain.rules.applicability import ApplicabilityFacts, assess_applicability

    result = assess_applicability(ApplicabilityFacts(None, None), evidence_ids=("manual:page:56",))

    assert result.status == "undetermined"
    assert result.missing_information == (
        "Confirmar cuántos vehículos intervinieron.",
        "Confirmar si existió colisión directa entre los dos vehículos.",
    )


def test_two_vehicles_with_direct_collision_is_applicable_at_the_gate() -> None:
    from domain.rules.applicability import ApplicabilityFacts, assess_applicability

    result = assess_applicability(ApplicabilityFacts(2, True), evidence_ids=("manual:page:56",))

    assert result.status == "applicable"
