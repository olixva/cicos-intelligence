"""Pure source- and operations-based measures for Langfuse experiment callbacks."""

from collections.abc import Sequence
from dataclasses import dataclass


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
