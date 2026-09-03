"""Deterministic, pure-function metrics for the source-grounded evaluation surface.

These tests are pure: no fixtures, no monkeypatching of module globals, no I/O.
The metrics implemented here back the eight-dimension Langfuse scorecard for
the question, claim, and router flows.
"""

from __future__ import annotations

import pytest


def test_decision_accuracy_exact_match() -> None:
    from infrastructure.adapters.outbound.evaluation.domain_evaluators import (
        decision_accuracy,
    )

    assert decision_accuracy(predicted="resolved", expected="resolved") == 1.0


def test_decision_accuracy_mismatch_returns_zero() -> None:
    from infrastructure.adapters.outbound.evaluation.domain_evaluators import (
        decision_accuracy,
    )

    assert decision_accuracy(predicted="resolved", expected="undetermined") == 0.0


def test_decision_accuracy_none_expected_returns_none() -> None:
    from infrastructure.adapters.outbound.evaluation.domain_evaluators import (
        decision_accuracy,
    )

    assert decision_accuracy(predicted="resolved", expected=None) is None


def test_macro_f1_balanced_classes() -> None:
    from infrastructure.adapters.outbound.evaluation.domain_evaluators import macro_f1

    # Class A: tp=2, fp=1, fn=0 → P=2/3, R=2/2 → F1=0.8
    # Class B: tp=1, fp=1, fn=1 → P=1/2, R=1/2 → F1=0.5
    tp = {"A": 2, "B": 1}
    fp = {"A": 1, "B": 1}
    fn = {"A": 0, "B": 1}
    assert macro_f1(tp, fp, fn) == pytest.approx((0.8 + 0.5) / 2)


def test_macro_f1_skips_missing_classes() -> None:
    """Classes absent from the confusion map do not contribute to the macro mean."""

    from infrastructure.adapters.outbound.evaluation.domain_evaluators import macro_f1

    tp = {"A": 2, "B": 0}
    fp = {"A": 1, "B": 0}
    fn = {"A": 0, "B": 0}
    # Only class A contributes (B has no support and would have 0/0).
    assert macro_f1(tp, fp, fn) == pytest.approx(0.8)


def test_macro_f1_perfect_returns_one() -> None:
    from infrastructure.adapters.outbound.evaluation.domain_evaluators import macro_f1

    tp = {"resolved": 3, "undetermined": 2}
    fp = {"resolved": 0, "undetermined": 0}
    fn = {"resolved": 0, "undetermined": 0}
    assert macro_f1(tp, fp, fn) == 1.0


def test_invented_facts_rate_no_inventions() -> None:
    from infrastructure.adapters.outbound.evaluation.domain_evaluators import (
        invented_facts_rate,
    )

    rate = invented_facts_rate(
        predicted_facts=["vehicle count is two", "weather is dry"],
        expected_facts=["vehicle count is two", "weather is dry"],
    )
    assert rate == 0.0


def test_invented_facts_rate_one_invention() -> None:
    from infrastructure.adapters.outbound.evaluation.domain_evaluators import (
        invented_facts_rate,
    )

    rate = invented_facts_rate(
        predicted_facts=["vehicle count is two", "weather is dry"],
        expected_facts=["vehicle count is two"],
    )
    assert rate == pytest.approx(0.5)


def test_invented_facts_rate_forbidden_fact_not_counted_as_invented() -> None:
    from infrastructure.adapters.outbound.evaluation.domain_evaluators import (
        invented_facts_rate,
    )

    rate = invented_facts_rate(
        predicted_facts=["vehicle count is two", "weather is dry"],
        expected_facts=["vehicle count is two"],
        forbidden_facts=("weather is dry",),
    )
    # 'weather is dry' is a forbidden fact, not an invention.
    assert rate == 0.0


def test_unjustified_resolution_rate_none_when_no_mismatch() -> None:
    from infrastructure.adapters.outbound.evaluation.domain_evaluators import (
        unjustified_resolution_rate,
    )

    rate = unjustified_resolution_rate(
        predicted_decisions=["resolved", "conditional"],
        expected_decisions=["resolved", "conditional"],
    )
    assert rate == 0.0


def test_unjustified_resolution_rate_counts_resolved_vs_undetermined() -> None:
    from infrastructure.adapters.outbound.evaluation.domain_evaluators import (
        unjustified_resolution_rate,
    )

    # 2 of 4 cases predict 'resolved' while the expected outcome is not resolved.
    rate = unjustified_resolution_rate(
        predicted_decisions=["resolved", "resolved", "conditional", "undetermined"],
        expected_decisions=["conditional", "undetermined", "conditional", "undetermined"],
    )
    assert rate == pytest.approx(0.5)


def test_abstention_correct_when_predicted_matches_expected_undetermined() -> None:
    from infrastructure.adapters.outbound.evaluation.domain_evaluators import (
        abstention_metrics,
    )

    correct, unnecessary = abstention_metrics(
        predicted_decisions=["undetermined", "conditional"],
        expected_decisions=["undetermined", "conditional"],
    )
    assert correct == 1.0
    assert unnecessary == 0.0


def test_abstention_unnecessary_when_predicted_resolved_but_expected_undetermined() -> None:
    from infrastructure.adapters.outbound.evaluation.domain_evaluators import (
        abstention_metrics,
    )

    correct, unnecessary = abstention_metrics(
        predicted_decisions=["resolved", "undetermined"],
        expected_decisions=["undetermined", "resolved"],
    )
    # First pair: predicted resolved but expected abstains → contributes to 'correct'
    # denominator (expected abstains) but not to the correct numerator.
    # Second pair: predicted abstains while expected resolved → contributes to
    # 'unnecessary' (numerator and denominator).
    assert correct == 0.0
    assert unnecessary == 1.0


def test_router_confusion_matrix_three_by_three() -> None:
    from infrastructure.adapters.outbound.evaluation.domain_evaluators import (
        router_confusion_matrix,
    )

    matrix = router_confusion_matrix(
        predicted_routes=["question", "claim", "clarification_required", "question"],
        expected_routes=["question", "claim", "claim", "clarification_required"],
    )
    assert matrix[("question", "question")] == 1
    assert matrix[("claim", "claim")] == 1
    assert matrix[("claim", "clarification_required")] == 1
    assert matrix[("clarification_required", "question")] == 1
    # Combinations not seen must not appear.
    assert ("question", "claim") not in matrix
    assert ("clarification_required", "clarification_required") not in matrix


def test_router_confusion_matrix_handles_missing_labels() -> None:
    from infrastructure.adapters.outbound.evaluation.domain_evaluators import (
        router_confusion_matrix,
    )

    # Only the (question, question) combination is observed.
    matrix = router_confusion_matrix(
        predicted_routes=["question"],
        expected_routes=["question"],
    )
    assert matrix == {("question", "question"): 1}


def test_evidence_reference_validity_all_known() -> None:
    from infrastructure.adapters.outbound.evaluation.domain_evaluators import (
        evidence_reference_validity,
    )

    rate = evidence_reference_validity(
        cited=["sha256:abc:page:1", "sha256:abc:page:2"],
        valid_pool={"sha256:abc:page:1", "sha256:abc:page:2", "sha256:abc:page:3"},
    )
    assert rate == 1.0


def test_evidence_reference_validity_one_unknown() -> None:
    from infrastructure.adapters.outbound.evaluation.domain_evaluators import (
        evidence_reference_validity,
    )

    rate = evidence_reference_validity(
        cited=["sha256:abc:page:1", "sha256:abc:page:99"],
        valid_pool={"sha256:abc:page:1", "sha256:abc:page:2"},
    )
    assert rate == pytest.approx(0.5)


def test_evidence_reference_validity_empty_cited_is_none() -> None:
    from infrastructure.adapters.outbound.evaluation.domain_evaluators import (
        evidence_reference_validity,
    )

    assert evidence_reference_validity(cited=[], valid_pool={"sha256:abc:page:1"}) is None
