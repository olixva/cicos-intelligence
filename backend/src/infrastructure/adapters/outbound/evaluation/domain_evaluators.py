"""Pure source- and operations-based measures for Langfuse experiment callbacks."""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

_ABSTAIN_DECISIONS = frozenset({"undetermined", "conditional", "not_assessed"})
_NON_RESOLVED_DECISIONS = frozenset({"conditional", "undetermined", "not_assessed"})
_ROUTER_LABELS = ("question", "claim", "clarification_required")


@dataclass(frozen=True, slots=True)
class CitationMetrics:
    """Precision and recall over identifiers that were actually delivered."""

    precision: float | None
    recall: float | None


def coverage(
    requirements: Sequence[Sequence[frozenset[str]]], delivered: frozenset[str]
) -> float | None:
    """Measure requirements met by one complete alternative evidence bundle."""

    if not requirements:
        return None
    covered = sum(
        any(bundle <= delivered for bundle in alternatives) for alternatives in requirements
    )
    return covered / len(requirements)


def citation_metrics(*, cited: frozenset[str], required: frozenset[str]) -> CitationMetrics:
    """Return identifier-level citation precision and recall without semantic claims."""

    shared = len(cited & required)
    return CitationMetrics(
        precision=shared / len(cited) if cited else None,
        recall=shared / len(required) if required else None,
    )


def cost_per_success(total_cost: float, successes: int) -> float | None:
    """Allocate all experiment cost over successful executions, if any."""

    if total_cost < 0:
        raise ValueError("total cost must be nonnegative")
    if type(successes) is not int or successes < 0:
        raise ValueError("successes must be a nonnegative integer")
    return total_cost / successes if successes else None


def decision_accuracy(*, predicted: str, expected: str | None) -> float | None:
    """Exact-match decision accuracy, with ``None`` signaling no expected label."""

    if expected is None:
        return None
    return 1.0 if predicted == expected else 0.0


def macro_f1(tp: Mapping[str, int], fp: Mapping[str, int], fn: Mapping[str, int]) -> float | None:
    """Unweighted mean of per-class F1 over the union of all observed class labels."""

    classes = set(tp) | set(fp) | set(fn)
    if not classes:
        return None
    per_class: list[float] = []
    for label in classes:
        true_positive = tp.get(label, 0)
        false_positive = fp.get(label, 0)
        false_negative = fn.get(label, 0)
        if true_positive + false_positive + false_negative == 0:
            # No support at all for this class → skip it from the macro mean.
            continue
        precision = true_positive / (true_positive + false_positive)
        recall = true_positive / (true_positive + false_negative)
        if precision + recall == 0:
            per_class.append(0.0)
        else:
            per_class.append(2 * precision * recall / (precision + recall))
    if not per_class:
        return None
    return sum(per_class) / len(per_class)


def _normalize_fact(fact: str) -> str:
    return fact.strip().casefold()


def invented_facts_rate(
    *,
    predicted_facts: Sequence[str],
    expected_facts: Sequence[str],
    forbidden_facts: Sequence[str] = (),
) -> float | None:
    """Share of predicted facts that are not in expected or forbidden pools.

    A ``forbidden`` fact is a known-bad ground-truth negative; it must not
    be counted as a model invention.
    """

    if not predicted_facts:
        return None
    allowed = {_normalize_fact(fact) for fact in expected_facts}
    allowed.update(_normalize_fact(fact) for fact in forbidden_facts)
    inventions = sum(1 for fact in predicted_facts if _normalize_fact(fact) not in allowed)
    return inventions / len(predicted_facts)


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
