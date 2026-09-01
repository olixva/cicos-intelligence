"""Deterministic metrics that complement native Langfuse and Ragas evaluation."""


def test_retrieving_rule_without_required_exception_is_not_sufficient() -> None:
    from infrastructure.adapters.outbound.evaluation.domain_evaluators import coverage

    requirement = ((frozenset({"rule", "exception"}),),)

    assert coverage(requirement, frozenset({"rule"})) == 0.0


def test_coverage_allows_any_complete_alternative_bundle() -> None:
    from infrastructure.adapters.outbound.evaluation.domain_evaluators import coverage

    requirements = (
        (frozenset({"rule", "exception"}), frozenset({"alternative"})),
        (frozenset({"second-rule"}),),
    )

    assert coverage(requirements, frozenset({"alternative", "second-rule"})) == 1.0


def test_empty_requirements_have_no_coverage_denominator() -> None:
    from infrastructure.adapters.outbound.evaluation.domain_evaluators import coverage

    assert coverage((), frozenset()) is None


def test_citation_precision_and_recall_distinguish_irrelevant_citations() -> None:
    from infrastructure.adapters.outbound.evaluation.domain_evaluators import citation_metrics

    result = citation_metrics(
        cited=frozenset({"rule", "irrelevant"}), required=frozenset({"rule", "exception"})
    )

    assert result.precision == 0.5
    assert result.recall == 0.5


def test_cost_per_success_uses_every_cost_and_no_zero_denominator() -> None:
    from infrastructure.adapters.outbound.evaluation.domain_evaluators import cost_per_success

    assert cost_per_success(12.0, 3) == 4.0
    assert cost_per_success(12.0, 0) is None
