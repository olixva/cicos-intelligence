"""A rule evaluation must carry its own inputs, result and evidence.

The audit forbids placeholder rules: the claim flow may only claim that
a rule ran if it can say which inputs it saw, what it concluded and
which manual page supports it.
"""

import pytest

from domain.models.rule_evaluation import RuleEvaluation
from domain.rules.ruleset import evaluate_ruleset

_EVIDENCE = ("sha256:" + "0" * 64 + ":page:56",)


def test_rule_evaluation_keeps_inputs_and_evidence() -> None:
    evaluation = RuleEvaluation(
        rule_id="cide-requires-two-vehicles",
        inputs=(("vehicle_count", "2"), ("direct_collision", "true")),
        result="matched",
        evidence_ids=_EVIDENCE,
        rationale="Dos vehículos con colisión directa.",
    )
    assert evaluation.inputs == (("vehicle_count", "2"), ("direct_collision", "true"))
    assert evaluation.result == "matched"


def test_rule_evaluation_rejects_a_matched_result_without_evidence() -> None:
    with pytest.raises(ValueError, match="evidence"):
        RuleEvaluation(
            rule_id="cide-requires-two-vehicles",
            inputs=(("vehicle_count", "2"),),
            result="matched",
            evidence_ids=(),
            rationale="Sin evidencia.",
        )


def test_rule_evaluation_rejects_an_empty_rationale() -> None:
    with pytest.raises(ValueError, match="rationale"):
        RuleEvaluation(
            rule_id="cide-requires-two-vehicles",
            inputs=(),
            result="insufficient_data",
            evidence_ids=(),
            rationale="   ",
        )


def test_rule_evaluation_rejects_an_empty_rule_id() -> None:
    with pytest.raises(ValueError, match="rule_id"):
        RuleEvaluation(
            rule_id="  ",
            inputs=(),
            result="not_matched",
            evidence_ids=(),
            rationale="Regla sin identificador.",
        )


def test_rule_evaluation_is_hashable_and_frozen() -> None:
    """Evaluations travel inside a frozen ClaimAnalysis; they must not mutate."""
    evaluation = RuleEvaluation(
        rule_id="cide-requires-two-vehicles",
        inputs=(("vehicle_count", "3"),),
        result="not_matched",
        evidence_ids=_EVIDENCE,
        rationale="Intervienen tres vehículos.",
    )
    assert hash(evaluation)
    with pytest.raises(AttributeError):
        evaluation.result = "matched"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# The shipped ruleset. These guard the delivery: a rule whose evidence stops
# resolving, or an attestation that decays, must fail loudly rather than let
# the claim workflow keep deciding on it.
# ---------------------------------------------------------------------------

import json  # noqa: E402
from pathlib import Path  # noqa: E402

from domain.rules.artifact_validation import (  # noqa: E402
    evidence_pool_from_publications,
    validate_ruleset,
)

_REPO = Path(__file__).resolve().parents[2]
_RULESET = _REPO / "data" / "rules" / "ruleset.v1.json"
_DOCUMENT_HASH = "b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344"


def test_shipped_ruleset_validates_with_a_complete_attestation() -> None:
    report = validate_ruleset(
        _RULESET,
        expected_document_hash=_DOCUMENT_HASH,
        evidence_pool=evidence_pool_from_publications([_REPO / "data" / "extractions"]),
    )
    assert report.errors == ()
    assert report.attestation_complete


def test_shipped_ruleset_covers_the_five_interview_accidents() -> None:
    """Each accident in the brief must have a rule that speaks to it."""
    rules = {rule["rule_id"] for rule in json.loads(_RULESET.read_text(encoding="utf-8"))["rules"]}
    assert {
        "cide-requires-two-vehicles",  # accidents 1 and 2
        "cide-requires-direct-collision",
        "chain-collision-excludes-convention",  # accident 2
        "third-vehicle-identified-excludes-convention",  # accident 3
        "ascide-b5-parked-vehicle",  # accident 3
        "ascide-b10-lane-change",  # accident 4
        "alcohol-does-not-exclude-convention",  # accident 5
        "ascide-traffic-light-amber",  # accident 1
        "cide-matrix-lookup",  # accident 1
    } <= rules


def test_every_shipped_rule_cites_evidence_and_a_reviewer() -> None:
    """A rule without a page behind it is exactly the placeholder the audit forbids."""
    for rule in json.loads(_RULESET.read_text(encoding="utf-8"))["rules"]:
        assert rule["evidence_ids"], rule["rule_id"]
        assert rule["reviewer_id"].strip(), rule["rule_id"]
        assert rule["description"].strip(), rule["rule_id"]


def test_no_shipped_attestation_carries_a_placeholder_hash() -> None:
    """A zeroed transcription hash would make the attestation decorative."""
    for artifact in (_RULESET, _REPO / "data" / "rules" / "cide-matrix.v1.json"):
        attestation = json.loads(artifact.read_text(encoding="utf-8"))["attestation"]
        for entry in attestation["transcriptions"]:
            assert entry["transcription_sha256"] != "0" * 64, artifact.name
        assert "pendiente" not in attestation["divergence_resolution"].lower()


def test_a_resolved_decision_requires_a_matched_rule() -> None:
    """The invariant that stops a conclusion with nothing deterministic behind it."""
    from domain.models.decision import ClaimAnalysis, InvalidDecisionError

    with pytest.raises(InvalidDecisionError, match="matched rule"):
        ClaimAnalysis(
            applicability="applicable",
            convention="CIDE",
            decision="resolved",
            party_ids=("A", "B"),
            facts=(),
            contradictions=(),
            conditions=(),
            missing_information=(),
            blocks=(),
            rules_evaluated=(),
        )


def test_an_inapplicable_convention_cannot_stay_conditional_either() -> None:
    """`resolved` ya estaba bloqueado; `conditional` sobre un Convenio ya
    descartado es el mismo error: no hay nada que condicionar, sólo declarar
    que no procede."""
    from domain.models.decision import ClaimAnalysis, InvalidDecisionError

    with pytest.raises(InvalidDecisionError, match="not_assessed"):
        ClaimAnalysis(
            applicability="not_applicable",
            convention=None,
            decision="conditional",
            party_ids=("A", "B"),
            facts=(),
            contradictions=(),
            conditions=("¿Cuál fue el primer impacto?",),
            missing_information=("¿Cuál fue el primer impacto?",),
            blocks=(),
        )


def test_a_resolved_decision_is_allowed_when_a_rule_matched() -> None:
    from domain.models.decision import ClaimAnalysis

    analysis = ClaimAnalysis(
        applicability="applicable",
        convention="CIDE",
        decision="resolved",
        party_ids=("A", "B"),
        facts=(),
        contradictions=(),
        conditions=(),
        missing_information=(),
        blocks=(),
        rules_evaluated=(
            RuleEvaluation(
                rule_id="cide-requires-two-vehicles",
                inputs=(("vehicle_count", "2"),),
                result="matched",
                evidence_ids=_EVIDENCE,
                rationale="Dos vehículos.",
            ),
        ),
    )
    assert analysis.decision == "resolved"


def test_shipped_lane_change_rule_matches_on_acknowledged_lane_change() -> None:
    """Regression for accident-04: b.10 must be machine-checkable, not just documented."""
    from infrastructure.config.rules_artifacts import load_rules_artifacts

    artifacts = load_rules_artifacts(
        _REPO / "data" / "rules",
        expected_document_hash=_DOCUMENT_HASH,
        evidence_roots=(_REPO / "data" / "extractions",),
    )
    (evaluation,) = [
        result
        for result in evaluate_ruleset(
            artifacts.rules,
            {"lane_change_acknowledged_by_both": "true", "contradictory_versions": "true"},
        )
        if result.rule_id == "ascide-b10-lane-change"
    ]
    assert evaluation.result == "matched"
    assert evaluation.evidence_ids


def test_shipped_lane_change_rule_does_not_match_without_disparity() -> None:
    from infrastructure.config.rules_artifacts import load_rules_artifacts

    artifacts = load_rules_artifacts(
        _REPO / "data" / "rules",
        expected_document_hash=_DOCUMENT_HASH,
        evidence_roots=(_REPO / "data" / "extractions",),
    )
    (evaluation,) = [
        result
        for result in evaluate_ruleset(
            artifacts.rules,
            {"lane_change_acknowledged_by_both": "true", "contradictory_versions": "false"},
        )
        if result.rule_id == "ascide-b10-lane-change"
    ]
    assert evaluation.result == "not_matched"


def test_shipped_amber_rule_matches_when_one_driver_admits_amber() -> None:
    from infrastructure.config.rules_artifacts import load_rules_artifacts

    artifacts = load_rules_artifacts(
        _REPO / "data" / "rules",
        expected_document_hash=_DOCUMENT_HASH,
        evidence_roots=(_REPO / "data" / "extractions",),
    )
    (evaluation,) = [
        result
        for result in evaluate_ruleset(
            artifacts.rules,
            {"traffic_light_junction": "true", "admitted_amber": "true"},
        )
        if result.rule_id == "ascide-traffic-light-amber"
    ]

    assert evaluation.result == "matched"
