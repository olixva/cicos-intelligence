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
