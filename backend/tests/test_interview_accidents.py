"""The five accidents from the interview brief, as an executable contract.

Four of the five fall outside the CIDE/ASCIDE conventions. The specification
is explicit that abstaining is the correct answer there — "no se exige
inventar una conclusión definitiva" — so these tests assert the reasoning the
system must show, not just the enum it lands on.
"""

from pathlib import Path

from domain.rules.ruleset import evaluate_ruleset
from infrastructure.config.rules_artifacts import load_rules_artifacts

_RULES = load_rules_artifacts(Path(__file__).resolve().parents[2] / "data" / "rules").rules


def _by_id(facts: dict[str, str]) -> dict[str, str]:
    """Run the shipped ruleset and index the outcome of every rule."""
    return {ev.rule_id: ev.result for ev in evaluate_ruleset(_RULES, facts)}


def test_accident_1_rear_end_at_a_red_light_stays_inside_the_convention() -> None:
    """Two vehicles, direct collision: nothing excludes the convention."""
    results = _by_id({"vehicle_count": "2", "direct_collision": "true", "chain_collision": "false"})
    assert results["cide-requires-two-vehicles"] == "not_matched"
    assert results["cide-requires-direct-collision"] == "not_matched"
    assert results["chain-collision-excludes-convention"] == "not_matched"


def test_accident_2_five_car_pileup_is_excluded_twice_over() -> None:
    """More than two vehicles AND a chain collision: two independent exclusions."""
    results = _by_id({"vehicle_count": "5", "direct_collision": "true", "chain_collision": "true"})
    assert results["cide-requires-two-vehicles"] == "matched"
    assert results["chain-collision-excludes-convention"] == "matched"


def test_accident_3_hit_and_run_on_a_parked_car_has_no_second_party() -> None:
    """Only one identified vehicle, so the two-vehicle requirement fails."""
    results = _by_id({"vehicle_count": "1", "direct_collision": "true"})
    assert results["cide-requires-two-vehicles"] == "matched"


def test_accident_4_lane_change_is_not_decided_automatically_yet() -> None:
    """The ASCIDE b.10 norm is documented but not machine-checkable today.

    It must report insufficient_data rather than be presented as applied.
    """
    results = _by_id({"vehicle_count": "2", "direct_collision": "true", "lane_change": "true"})
    assert results["ascide-b10-lane-change"] == "insufficient_data"
    assert results["cide-requires-two-vehicles"] == "not_matched"


def test_accident_5_alcohol_does_not_exclude_the_convention() -> None:
    """Page 9 says so outright; the rule exists to stop a wrong exclusion."""
    results = _by_id(
        {
            "vehicle_count": "2",
            "direct_collision": "true",
            "driver_under_influence": "true",
        }
    )
    assert results["alcohol-does-not-exclude-convention"] == "matched"
    assert results["cide-requires-two-vehicles"] == "not_matched"


def test_no_rule_is_ever_matched_without_the_evidence_that_supports_it() -> None:
    evaluations = evaluate_ruleset(
        _RULES, {"vehicle_count": "5", "direct_collision": "true", "chain_collision": "true"}
    )
    for evaluation in evaluations:
        if evaluation.result == "matched":
            assert evaluation.evidence_ids, evaluation.rule_id


def test_every_rule_reports_something_so_the_interface_can_show_its_work() -> None:
    evaluations = evaluate_ruleset(_RULES, {"vehicle_count": "2"})
    assert len(evaluations) == len(_RULES)
    assert {e.rule_id for e in evaluations} == {r.rule_id for r in _RULES}
