"""The ruleset evaluator runs the reviewed artifact, not hand-written logic.

Conditions live in the signed ruleset so a human reviewer can read what the
system will decide. The evaluator only executes a tiny closed predicate
language over the facts extracted from the claim, and it always reports one
evaluation per rule so the interface can show what ran and what could not.
"""

import pytest

from domain.models.rule_evaluation import RuleEvaluation
from domain.rules.ruleset import LoadedRule, RulesetError, evaluate_ruleset

_EV = ("sha256:" + "b" * 64 + ":page:56",)


def _rule(rule_id: str, applies_when: dict[str, object] | None, **kw: object) -> LoadedRule:
    return LoadedRule(
        rule_id=rule_id,
        kind=str(kw.get("kind", "applicability")),
        description=str(kw.get("description", "Regla de prueba.")),
        prerequisites=tuple(kw.get("prerequisites", ())),  # type: ignore[arg-type]
        outcome=str(kw.get("outcome", "consecuencia")),
        evidence_ids=_EV,
        applies_when=applies_when,
    )


def test_a_rule_whose_condition_holds_is_matched_with_its_evidence() -> None:
    rule = _rule("dos-vehiculos", {"field": "vehicle_count", "op": "ne", "value": "2"})
    (result,) = evaluate_ruleset((rule,), {"vehicle_count": "5"})
    assert result.result == "matched"
    assert result.evidence_ids == _EV
    assert ("vehicle_count", "5") in result.inputs


def test_a_rule_whose_condition_fails_is_reported_as_not_matched() -> None:
    rule = _rule("dos-vehiculos", {"field": "vehicle_count", "op": "ne", "value": "2"})
    (result,) = evaluate_ruleset((rule,), {"vehicle_count": "2"})
    assert result.result == "not_matched"


def test_a_missing_fact_is_insufficient_data_and_never_a_guess() -> None:
    rule = _rule("dos-vehiculos", {"field": "vehicle_count", "op": "ne", "value": "2"})
    (result,) = evaluate_ruleset((rule,), {})
    assert result.result == "insufficient_data"
    assert result.inputs == ()


def test_every_rule_produces_an_evaluation_even_when_none_match() -> None:
    rules = (
        _rule("a", {"field": "x", "op": "eq", "value": "1"}),
        _rule("b", {"field": "y", "op": "eq", "value": "1"}),
        _rule("c", None, prerequisites=("z",)),
    )
    results = evaluate_ruleset(rules, {"x": "2"})
    assert [r.rule_id for r in results] == ["a", "b", "c"]
    assert {r.result for r in results} == {"not_matched", "insufficient_data"}


def test_a_rule_without_a_condition_reports_insufficient_data_not_a_match() -> None:
    """A rule we cannot evaluate yet must never be presented as satisfied."""
    rule = _rule("b10-cambio-carril", None, prerequisites=("lane_change_acknowledged_by_both",))
    (result,) = evaluate_ruleset((rule,), {"lane_change_acknowledged_by_both": "true"})
    assert result.result == "insufficient_data"


def test_boolean_operators_read_the_extracted_string_values() -> None:
    rule = _rule("cadena", {"field": "chain_collision", "op": "is_true"})
    (matched,) = evaluate_ruleset((rule,), {"chain_collision": "true"})
    (unmatched,) = evaluate_ruleset((rule,), {"chain_collision": "false"})
    assert matched.result == "matched"
    assert unmatched.result == "not_matched"


def test_all_and_any_compose_conditions() -> None:
    both = {"all": [{"field": "a", "op": "is_true"}, {"field": "b", "op": "is_true"}]}
    either = {"any": [{"field": "a", "op": "is_true"}, {"field": "b", "op": "is_true"}]}
    assert evaluate_ruleset((_rule("r", both),), {"a": "true", "b": "true"})[0].result == "matched"
    assert evaluate_ruleset((_rule("r", both),), {"a": "true", "b": "false"})[0].result == (
        "not_matched"
    )
    assert evaluate_ruleset((_rule("r", either),), {"a": "true", "b": "false"})[0].result == (
        "matched"
    )


def test_an_unknown_operator_is_rejected_rather_than_silently_ignored() -> None:
    rule = _rule("r", {"field": "a", "op": "regex_match", "value": ".*"})
    with pytest.raises(RulesetError, match="regex_match"):
        evaluate_ruleset((rule,), {"a": "x"})


def test_the_rationale_names_the_rule_and_what_was_seen() -> None:
    rule = _rule(
        "cadena",
        {"field": "chain_collision", "op": "is_true"},
        description="La colisión en cadena no se tramita por Convenio.",
    )
    (result,) = evaluate_ruleset((rule,), {"chain_collision": "true"})
    assert isinstance(result, RuleEvaluation)
    assert "cadena" in result.rationale.lower()
