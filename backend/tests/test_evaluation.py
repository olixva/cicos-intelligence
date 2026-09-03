"""Evaluacion: evaluadores deterministas, golden set y metricas de evidencia."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

import pytest

from application.models.query import QueryExecution, QueryInput, QuestionAnswer

# --------------------------------------------------------------------------
# Deterministic, pure-function metrics for the source-grounded evaluation surface.
#
# These tests are pure: no fixtures, no monkeypatching of module globals, no I/O.
# The metrics implemented here back the eight-dimension Langfuse scorecard for
# the question, claim, and router flows.
# --------------------------------------------------------------------------


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


# --------------------------------------------------------------------------
# Deterministic integrity gates for frozen golden-set releases.
# --------------------------------------------------------------------------


def _item(
    *, case_id: str = "fixture-case-1", family_id: str = "fixture-family-1"
) -> dict[str, object]:
    return {
        "input": {
            "text": "Pregunta técnica sin contenido del manual.",
            "language": "es",
            "clarifications": [],
        },
        "expected_output": {
            "reference": "Respuesta técnica de fixture.",
            "decisions": {"intent": "question", "answer_status": "answered"},
            "requirements": [
                {"requirement_id": "requirement-1", "description": "Explica el fixture."}
            ],
            "acceptable_alternatives": [],
            "forbidden_facts": ["No inventar una segunda regla."],
            "evidence_requirements": [
                {
                    "requirement_id": "requirement-1",
                    "any_of": [
                        {
                            "bundle_id": "bundle-and",
                            "all_of": ["fixture:page:1", "fixture:page:2"],
                        },
                        {"bundle_id": "bundle-or", "all_of": ["fixture:page:3"]},
                    ],
                }
            ],
        },
        "metadata": {
            "case_id": case_id,
            "family_id": family_id,
            "partition": "development",
            "review_status": "adjudicated",
            "provenance": {
                "kind": "technical_fixture",
                "source_ids": ["test_golden_integrity"],
            },
            "language": "es",
            "expected_intent": "question",
            "review": {
                "reviewer_ids": ["technical-validator-fixture"],
                "independent_resolution_checked": True,
                "evidence_checked": True,
                "adversarial_checked": True,
                "adjudication_note": "Fixture used only to test release machinery.",
                "open_discrepancies": [],
            },
        },
    }


def _evidence_ids() -> frozenset[str]:
    return frozenset({"fixture:page:1", "fixture:page:2", "fixture:page:3"})


def test_family_cannot_cross_development_and_holdout() -> None:
    from infrastructure.adapters.outbound.evaluation.release_validation import (
        check_family_splits,
    )

    with pytest.raises(ValueError, match="family"):
        check_family_splits([("family-1", "development"), ("family-1", "holdout")])


@pytest.mark.parametrize("review_status", ["candidate", "in_review", "quarantined"])
def test_unfinished_or_quarantined_case_cannot_be_released(review_status: str) -> None:
    from infrastructure.adapters.outbound.evaluation.release_validation import validate_release

    item = _item()
    cast(dict[str, object], item["metadata"])["review_status"] = review_status

    with pytest.raises(ValueError, match="review"):
        validate_release(
            [item], existing_evidence_ids=_evidence_ids(), allow_technical_fixtures=True
        )


def test_expected_answer_cannot_leak_into_native_input() -> None:
    from infrastructure.adapters.outbound.evaluation.release_validation import validate_release

    item = _item()
    cast(dict[str, object], item["input"])["expected_answer"] = "LEAKED_REFERENCE"

    with pytest.raises(ValueError, match="schema"):
        validate_release(
            [item], existing_evidence_ids=_evidence_ids(), allow_technical_fixtures=True
        )


def test_unknown_evidence_blocks_release() -> None:
    from infrastructure.adapters.outbound.evaluation.release_validation import validate_release

    with pytest.raises(ValueError, match="fixture:page:3"):
        validate_release(
            [_item()],
            existing_evidence_ids={"fixture:page:1", "fixture:page:2"},
            allow_technical_fixtures=True,
        )


def test_empty_and_or_evidence_expression_is_invalid() -> None:
    from infrastructure.adapters.outbound.evaluation.release_validation import validate_release

    item = _item()
    expected = cast(dict[str, object], item["expected_output"])
    requirements = cast(list[dict[str, object]], expected["evidence_requirements"])
    requirements[0]["any_of"] = []

    with pytest.raises(ValueError, match="schema"):
        validate_release(
            [item], existing_evidence_ids=_evidence_ids(), allow_technical_fixtures=True
        )


def test_incomplete_review_checks_block_release() -> None:
    from infrastructure.adapters.outbound.evaluation.release_validation import validate_release

    item = _item()
    review = cast(dict[str, object], cast(dict[str, object], item["metadata"])["review"])
    review["adversarial_checked"] = False

    with pytest.raises(ValueError, match="review"):
        validate_release(
            [item], existing_evidence_ids=_evidence_ids(), allow_technical_fixtures=True
        )


@pytest.mark.parametrize("value", ["yes", 1, "on"])
def test_review_flags_must_be_json_booleans(value: object) -> None:
    from infrastructure.adapters.outbound.evaluation.release_validation import validate_release

    item = _item()
    review = cast(dict[str, object], cast(dict[str, object], item["metadata"])["review"])
    review["independent_resolution_checked"] = value

    with pytest.raises(ValueError, match="schema"):
        validate_release(
            [item], existing_evidence_ids=_evidence_ids(), allow_technical_fixtures=True
        )


def test_release_manifest_hashes_canonical_jsonl_and_schema() -> None:
    from infrastructure.adapters.outbound.evaluation.golden_schema import canonical_schema_bytes
    from infrastructure.adapters.outbound.evaluation.release_validation import (
        build_release_manifest,
        canonical_jsonl,
    )

    first = _item(case_id="fixture-case-1", family_id="fixture-family-1")
    second = deepcopy(first)
    cast(dict[str, object], second["metadata"])["case_id"] = "fixture-case-2"
    schema = canonical_schema_bytes()

    content = canonical_jsonl(
        [first, second],
        existing_evidence_ids=_evidence_ids(),
        allow_technical_fixtures=True,
    )
    manifest = build_release_manifest(
        allow_technical_fixtures=True,
        dataset_name="technical-fixture",
        dataset_version="v1",
        items=[first, second],
        schema=schema,
        existing_evidence_ids=_evidence_ids(),
    )

    assert content.endswith(b"\n")
    assert manifest.item_count == 2
    assert manifest.case_ids == ("fixture-case-1", "fixture-case-2")
    assert manifest.content_sha256 == sha256(content).hexdigest()
    assert manifest.schema_sha256 == sha256(schema).hexdigest()
    assert manifest.partition_counts == (("development", 2), ("holdout", 0))


def test_release_manifest_rejects_bytes_that_are_not_the_canonical_schema() -> None:
    from infrastructure.adapters.outbound.evaluation.release_validation import (
        build_release_manifest,
    )

    with pytest.raises(ValueError, match="schema"):
        build_release_manifest(
            allow_technical_fixtures=True,
            dataset_name="technical-fixture",
            dataset_version="v1",
            items=[_item()],
            schema=b"not a JSON schema\n",
            existing_evidence_ids=_evidence_ids(),
        )


def test_release_manifest_partition_counts_are_immutable() -> None:
    from infrastructure.adapters.outbound.evaluation.golden_schema import canonical_schema_bytes
    from infrastructure.adapters.outbound.evaluation.release_validation import (
        build_release_manifest,
    )

    manifest = build_release_manifest(
        allow_technical_fixtures=True,
        dataset_name="technical-fixture",
        dataset_version="v1",
        items=[_item()],
        schema=canonical_schema_bytes(),
        existing_evidence_ids=_evidence_ids(),
    )

    with pytest.raises(TypeError):
        manifest.partition_counts[0] = ("development", 99)  # type: ignore[index]


def test_release_manifest_rejects_an_adulterated_deserialized_identity() -> None:
    from infrastructure.adapters.outbound.evaluation.release_validation import ReleaseManifest

    with pytest.raises(ValueError):
        ReleaseManifest.model_validate(
            {
                "schema_version": "not-current",
                "dataset_name": "technical-fixture",
                "dataset_version": "v1",
                "item_count": -5,
                "case_ids": [],
                "partition_counts": [["development", -9], ["development", 999]],
                "content_sha256": "not-a-hash",
                "schema_sha256": "also-not-a-hash",
            }
        )


def test_committed_schema_artifact_matches_the_release_schema() -> None:
    from infrastructure.adapters.outbound.evaluation.golden_schema import canonical_schema_bytes

    artifact = Path(__file__).parents[2] / "docs" / "evaluation" / "golden-schema.json"

    assert artifact.read_bytes() == canonical_schema_bytes()


# --------------------------------------------------------------------------
# Golden references must never cross into the evaluated question use case.
# --------------------------------------------------------------------------


@dataclass
class _SpyAnswerQuestion:
    received: list[QueryInput]

    async def execute(self, query: QueryInput) -> QueryExecution:
        self.received.append(query)
        return QueryExecution(result=QuestionAnswer("insufficient_evidence", ()), context=())


class _DatasetItem:
    input: Any = {"text": "Pregunta del usuario", "language": "es"}
    expected_output: Any = {"reference": "REFERENCE_SENTINEL"}
    metadata: Any = {"case_id": "fixture-case"}


def test_experiment_task_selects_only_native_input_fields() -> None:
    from infrastructure.adapters.outbound.evaluation.langfuse_experiments import build_question_task

    spy = _SpyAnswerQuestion(received=[])
    payload = asyncio.run(build_question_task(spy)(item=_DatasetItem()))

    assert spy.received == [QueryInput("Pregunta del usuario", "es")]
    assert "REFERENCE_SENTINEL" not in str(spy.received)
    assert payload["answer_text"] == ""
    assert payload["context"] == []


# --------------------------------------------------------------------------
# Deterministic metrics that complement native Langfuse and Ragas evaluation.
# --------------------------------------------------------------------------


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
