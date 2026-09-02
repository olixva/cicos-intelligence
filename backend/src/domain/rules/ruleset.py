"""Deterministic evaluation of the reviewed ruleset artifact.

The conditions live in ``data/rules/ruleset.v1.json`` rather than in code, so
a human reviewer reads exactly what the system will decide and signs it. This
module only executes a tiny closed predicate language over the facts extracted
from the claim.

Two properties matter more than expressiveness:

* One evaluation per rule, always. The interface has to be able to show what
  ran, what did not hold and what could not be checked.
* A fact that is absent yields ``insufficient_data``, never a guess. An
  unevaluable rule is never reported as satisfied.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

from domain.models.rule_evaluation import RuleEvaluation


class RulesetError(ValueError):
    """Raised when a rule uses a construct outside the closed predicate language."""


_TRUE = frozenset({"true", "sí", "si", "yes", "1"})
_FALSE = frozenset({"false", "no", "0"})


@dataclass(frozen=True, slots=True)
class LoadedRule:
    """One rule as authored in the signed artifact."""

    rule_id: str
    kind: str
    description: str
    prerequisites: tuple[str, ...]
    outcome: str | None
    evidence_ids: tuple[str, ...]
    applies_when: dict[str, object] | None = None


def evaluate_ruleset(
    rules: Sequence[LoadedRule], facts: Mapping[str, str]
) -> tuple[RuleEvaluation, ...]:
    """Return one evaluation per rule, in the artifact's order."""
    return tuple(_evaluate(rule, facts) for rule in rules)


def _evaluate(rule: LoadedRule, facts: Mapping[str, str]) -> RuleEvaluation:
    condition = rule.applies_when
    if not condition:
        # The rule is documented but not yet machine-checkable. Saying so is
        # the honest outcome; claiming it matched would be an invention.
        return RuleEvaluation(
            rule_id=rule.rule_id,
            inputs=(),
            result="insufficient_data",
            evidence_ids=(),
            rationale=(
                f"{rule.description} No se evalúa automáticamente: la regla no declara "
                "una condición verificable sobre los hechos extraídos."
            ),
        )

    used = _fields(condition)
    missing = tuple(name for name in used if name not in facts)
    if missing:
        return RuleEvaluation(
            rule_id=rule.rule_id,
            inputs=(),
            result="insufficient_data",
            evidence_ids=(),
            rationale=(f"{rule.description} Faltan hechos para evaluarla: {', '.join(missing)}."),
        )

    inputs = tuple((name, facts[name]) for name in used)
    holds = _holds(condition, facts)
    return RuleEvaluation(
        rule_id=rule.rule_id,
        inputs=inputs,
        result="matched" if holds else "not_matched",
        evidence_ids=rule.evidence_ids if holds else (),
        rationale=(
            f"{rule.description} {'Se cumple' if holds else 'No se cumple'} con "
            f"{', '.join(f'{k}={v}' for k, v in inputs)}."
        ),
    )


def _fields(condition: Mapping[str, object]) -> tuple[str, ...]:
    """Collect every fact name the condition reads, preserving order."""
    if "all" in condition or "any" in condition:
        names: list[str] = []
        for branch in _compound_branches(condition):
            for name in _fields(branch):
                if name not in names:
                    names.append(name)
        return tuple(names)
    field = condition.get("field")
    if not isinstance(field, str) or not field:
        raise RulesetError(f"condition without a field: {condition!r}")
    return (field,)


def _holds(condition: Mapping[str, object], facts: Mapping[str, str]) -> bool:
    if "all" in condition:
        return all(_holds(branch, facts) for branch in _compound_branches(condition))
    if "any" in condition:
        return any(_holds(branch, facts) for branch in _compound_branches(condition))

    field = str(condition["field"])
    op = condition.get("op")
    actual = facts[field]
    match op:
        case "eq":
            return actual == str(condition["value"])
        case "ne":
            return actual != str(condition["value"])
        case "gt":
            return _number(actual) > _number(str(condition["value"]))
        case "lt":
            return _number(actual) < _number(str(condition["value"]))
        case "is_true":
            return actual.strip().lower() in _TRUE
        case "is_false":
            return actual.strip().lower() in _FALSE
        case _:
            raise RulesetError(f"unknown ruleset operator: {op!r}")


def _number(value: str) -> float:
    try:
        return float(value)
    except ValueError as error:
        raise RulesetError(f"numeric comparison over a non-numeric value: {value!r}") from error


def _compound_branches(condition: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    """Return validated branches for the closed ``all``/``any`` operators."""
    value = condition.get("all") if "all" in condition else condition.get("any")
    if not isinstance(value, list):
        raise RulesetError(f"compound condition branches must be a list: {condition!r}")
    branches: list[Mapping[str, object]] = []
    for raw_branch in cast(list[object], value):
        if not isinstance(raw_branch, dict):
            raise RulesetError(f"condition branch must be an object: {raw_branch!r}")
        branch = cast(dict[object, object], raw_branch)
        if not all(isinstance(key, str) for key in branch):
            raise RulesetError(f"condition branch must use string keys: {raw_branch!r}")
        branches.append(cast(dict[str, object], branch))
    return tuple(branches)


def fact_names(rules: Sequence[LoadedRule]) -> tuple[str, ...]:
    """Return every fact name the ruleset consults, in artifact order.

    The extractor is prompted with exactly these, so a rule can never depend
    on a fact nothing was ever asked to extract.
    """

    names: list[str] = []
    for rule in rules:
        candidates = list(rule.prerequisites)
        if rule.applies_when:
            candidates = list(_fields(rule.applies_when)) + candidates
        for name in candidates:
            if name not in names:
                names.append(name)
    return tuple(names)
