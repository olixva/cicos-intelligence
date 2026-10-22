"""Pure source- and operations-based measures for Langfuse experiment callbacks."""

from collections.abc import Collection, Mapping, Sequence
from typing import cast

_ABSTAIN_DECISIONS = frozenset({"undetermined", "conditional", "not_assessed"})
_NON_RESOLVED_DECISIONS = frozenset({"conditional", "undetermined", "not_assessed"})
_ROUTER_LABELS = ("question", "claim", "clarification_required")


def decision_accuracy(*, predicted: str, expected: str | None) -> float | None:
    """Exact-match decision accuracy, with ``None`` signaling no expected label."""

    if expected is None:
        return None
    return 1.0 if predicted == expected else 0.0


def unjustified_resolution_rate(
    *,
    predicted_decisions: Sequence[str],
    expected_decisions: Sequence[str],
) -> float | None:
    """Fraction of cases where the model decided 'resolved' against a non-resolved reference."""

    if not predicted_decisions:
        return None
    if len(predicted_decisions) != len(expected_decisions):
        raise ValueError("predicted and expected decisions must align in length")
    mismatches = sum(
        1
        for predicted, expected in zip(predicted_decisions, expected_decisions, strict=True)
        if predicted == "resolved" and expected in _NON_RESOLVED_DECISIONS
    )
    return mismatches / len(predicted_decisions)


def over_resolution_rate_against_reference(
    *, predicted_decisions: Sequence[str], expected_decisions: Sequence[str]
) -> float | None:
    """Measure resolutions against references that require an abstention."""

    return unjustified_resolution_rate(
        predicted_decisions=predicted_decisions,
        expected_decisions=expected_decisions,
    )


def resolution_support_rate(*, result: Mapping[str, object]) -> float | None:
    """Check a resolved result has structured actor, matched rule and evidence.

    ``None`` means the result does not expose enough structure to score it. In
    particular, an actor is never recovered from explanatory free text.
    """

    if result.get("decision") != "resolved":
        return None
    actor = result.get("actor")
    if not isinstance(actor, str) or not actor.strip():
        return None
    rules = result.get("rules_evaluated")
    if not isinstance(rules, (list, tuple)):
        return None
    for raw_rule in cast(Sequence[object], rules):
        if not isinstance(raw_rule, Mapping):
            continue
        rule = cast(Mapping[str, object], raw_rule)
        if rule.get("result") != "matched":
            continue
        evidence_ids = rule.get("evidence_ids")
        if isinstance(evidence_ids, (list, tuple)) and any(
            isinstance(evidence_id, str) and evidence_id.strip()
            for evidence_id in cast(Sequence[object], evidence_ids)
        ):
            return 1.0
    return 0.0


def abstention_metrics(
    *,
    predicted_decisions: Sequence[str],
    expected_decisions: Sequence[str],
) -> tuple[float | None, float | None]:
    """Calibration of the model's abstention behaviour, conditioned on abstention.

    Both rates share the same denominator: the number of cases where the
    model actually abstained. ``None`` indicates the model never abstained,
    so neither rate is defined.
    """

    if len(predicted_decisions) != len(expected_decisions):
        raise ValueError("predicted and expected decisions must align in length")
    correct = sum(
        1
        for predicted, expected in zip(predicted_decisions, expected_decisions, strict=True)
        if predicted in _ABSTAIN_DECISIONS and expected in _ABSTAIN_DECISIONS
    )
    unnecessary = sum(
        1
        for predicted, expected in zip(predicted_decisions, expected_decisions, strict=True)
        if predicted in _ABSTAIN_DECISIONS and expected == "resolved"
    )
    abstentions = correct + unnecessary
    if abstentions == 0:
        return (None, None)
    return (correct / abstentions, unnecessary / abstentions)


def router_confusion_matrix(
    *,
    predicted_routes: Sequence[str],
    expected_routes: Sequence[str],
) -> dict[tuple[str, str], int]:
    """Closed-enum confusion matrix keyed by ``(expected, predicted)``."""

    if len(predicted_routes) != len(expected_routes):
        raise ValueError("predicted and expected routes must align in length")
    matrix: dict[tuple[str, str], int] = {}
    for expected, predicted in zip(expected_routes, predicted_routes, strict=True):
        if expected not in _ROUTER_LABELS or predicted not in _ROUTER_LABELS:
            raise ValueError("router decision is not a closed-enum label")
        matrix[(expected, predicted)] = matrix.get((expected, predicted), 0) + 1
    return matrix


def evidence_reference_validity(
    *, cited: Sequence[str], valid_pool: Collection[str]
) -> float | None:
    """Share of cited identifiers that resolve against the closed valid pool."""

    if not cited:
        return None
    pool = set(valid_pool)
    valid = sum(1 for evidence_id in cited if evidence_id in pool)
    return valid / len(cited)
