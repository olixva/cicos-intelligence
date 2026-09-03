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


def test_an_exclusion_rule_that_does_not_fire_is_not_described_as_unmet() -> None:
    """Regresión de legibilidad: la mayoría de puertas son reglas de exclusión.

    `cide-requires-two-vehicles` se activa cuando `vehicle_count != 2`. El texto
    anterior decía «No se cumple con vehicle_count=2», que el lector interpreta
    como «no hay dos vehículos» —justo lo contrario de lo ocurrido—.
    """
    rule = _rule(
        "cide-requires-two-vehicles",
        {"field": "vehicle_count", "op": "ne", "value": "2"},
        description="Los Convenios exigen la intervención de sólo dos vehículos.",
    )
    (result,) = evaluate_ruleset((rule,), {"vehicle_count": "2"})

    assert result.result == "not_matched"
    assert "No se activa con vehicle_count=2" in result.rationale
    assert "No se cumple" not in result.rationale


def test_a_rule_that_fires_states_the_consequence_its_reviewer_signed() -> None:
    rule = _rule(
        "cide-requires-two-vehicles",
        {"field": "vehicle_count", "op": "ne", "value": "2"},
        outcome="vehicle_count != 2 ⇒ Convenio no aplicable.",
    )
    (result,) = evaluate_ruleset((rule,), {"vehicle_count": "5"})

    assert result.result == "matched"
    assert "Se activa con vehicle_count=5" in result.rationale
    assert "Convenio no aplicable" in result.rationale


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


def test_a_non_object_condition_branch_is_rejected_at_the_ruleset_boundary() -> None:
    """A malformed compound condition must not escape as an AttributeError."""
    rule = _rule("r", {"all": ["not-a-condition"]})

    with pytest.raises(RulesetError, match="condition branch"):
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


def test_is_false_or_absent_fires_when_the_fact_is_missing() -> None:
    """Guard negativa: la regla debe disparar por defecto cuando el hecho
    simplemente no consta en el relato. Semántica intencional para
    ``ascide-b6-exit-from-parking`` (la nota de la regla dice explícitamente:
    «mientras exit_disputed_as_incorporation no conste como false, la regla
    no decide» — pero el motor lo modeló como ``is_false`` estricto, lo que
    rompe el caso normal en el que el hecho no se menciona)."""

    rule = _rule(
        "ascide-b6-exit-from-parking",
        {
            "all": [
                {"field": "exit_manoeuvre_by", "op": "ne", "value": ""},
                {"field": "exit_disputed_as_incorporation", "op": "is_false_or_absent"},
            ]
        },
        kind="manoeuvre",
    )
    (result,) = evaluate_ruleset((rule,), {"exit_manoeuvre_by": "A"})

    assert result.result == "matched"
    assert result.evidence_ids == _EV
    # El campo opcional no aparece en inputs porque no se consultó en facts.
    assert all(name != "exit_disputed_as_incorporation" for name, _ in result.inputs)


def test_is_false_or_absent_fires_when_the_fact_is_explicitly_false() -> None:
    rule = _rule(
        "ascide-b6-exit-from-parking",
        {
            "all": [
                {"field": "exit_manoeuvre_by", "op": "ne", "value": ""},
                {"field": "exit_disputed_as_incorporation", "op": "is_false_or_absent"},
            ]
        },
    )
    (result,) = evaluate_ruleset(
        (rule,),
        {"exit_manoeuvre_by": "A", "exit_disputed_as_incorporation": "false"},
    )
    assert result.result == "matched"


def test_is_false_or_absent_does_not_fire_when_the_fact_is_true() -> None:
    """Si el relato afirma explícitamente que la maniobra está disputada
    como incorporación, la regla NO debe disparar — eso es justo lo que el
    guard negativo protege."""

    rule = _rule(
        "ascide-b6-exit-from-parking",
        {
            "all": [
                {"field": "exit_manoeuvre_by", "op": "ne", "value": ""},
                {"field": "exit_disputed_as_incorporation", "op": "is_false_or_absent"},
            ]
        },
    )
    (result,) = evaluate_ruleset(
        (rule,),
        {"exit_manoeuvre_by": "A", "exit_disputed_as_incorporation": "true"},
    )
    assert result.result == "not_matched"
    assert result.evidence_ids == ()


def test_is_false_still_treats_absent_as_insufficient_data() -> None:
    """El operador ``is_false`` (estricto) NO cambia su semántica. Si el
    hecho falta, la regla sigue marcando ``insufficient_data`` — eso es
    deliberado para reglas como ``cide-requires-direct-collision`` donde la
    intención es "si NO hubo colisión directa, no aplica" (hecho ausente
    = desconocido, no decisión)."""

    rule = _rule(
        "cide-requires-direct-collision",
        {"field": "direct_collision", "op": "is_false"},
    )
    (result,) = evaluate_ruleset((rule,), {})
    assert result.result == "insufficient_data"
