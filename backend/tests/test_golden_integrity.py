"""Deterministic integrity gates for frozen golden-set releases."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import cast

import pytest


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
        validate_release([item], existing_evidence_ids=_evidence_ids())


def test_expected_answer_cannot_leak_into_native_input() -> None:
    from infrastructure.adapters.outbound.evaluation.release_validation import validate_release

    item = _item()
    cast(dict[str, object], item["input"])["expected_answer"] = "LEAKED_REFERENCE"

    with pytest.raises(ValueError, match="schema"):
        validate_release([item], existing_evidence_ids=_evidence_ids())


def test_unknown_evidence_blocks_release() -> None:
    from infrastructure.adapters.outbound.evaluation.release_validation import validate_release

    with pytest.raises(ValueError, match="fixture:page:3"):
        validate_release([_item()], existing_evidence_ids={"fixture:page:1", "fixture:page:2"})


def test_empty_and_or_evidence_expression_is_invalid() -> None:
    from infrastructure.adapters.outbound.evaluation.release_validation import validate_release

    item = _item()
    expected = cast(dict[str, object], item["expected_output"])
    requirements = cast(list[dict[str, object]], expected["evidence_requirements"])
    requirements[0]["any_of"] = []

    with pytest.raises(ValueError, match="schema"):
        validate_release([item], existing_evidence_ids=_evidence_ids())


def test_incomplete_review_checks_block_release() -> None:
    from infrastructure.adapters.outbound.evaluation.release_validation import validate_release

    item = _item()
    review = cast(dict[str, object], cast(dict[str, object], item["metadata"])["review"])
    review["adversarial_checked"] = False

    with pytest.raises(ValueError, match="review"):
        validate_release([item], existing_evidence_ids=_evidence_ids())


@pytest.mark.parametrize("value", ["yes", 1, "on"])
def test_review_flags_must_be_json_booleans(value: object) -> None:
    from infrastructure.adapters.outbound.evaluation.release_validation import validate_release

    item = _item()
    review = cast(dict[str, object], cast(dict[str, object], item["metadata"])["review"])
    review["independent_resolution_checked"] = value

    with pytest.raises(ValueError, match="schema"):
        validate_release([item], existing_evidence_ids=_evidence_ids())


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

    content = canonical_jsonl([first, second], existing_evidence_ids=_evidence_ids())
    manifest = build_release_manifest(
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
        dataset_name="technical-fixture",
        dataset_version="v1",
        items=[_item()],
        schema=canonical_schema_bytes(),
        existing_evidence_ids=_evidence_ids(),
    )

    with pytest.raises(TypeError):
        manifest.partition_counts[0] = ("development", 99)  # type: ignore[index]


def test_committed_schema_artifact_matches_the_release_schema() -> None:
    from infrastructure.adapters.outbound.evaluation.golden_schema import canonical_schema_bytes

    artifact = Path(__file__).parents[2] / "docs" / "evaluation" / "golden-schema.json"

    assert artifact.read_bytes() == canonical_schema_bytes()
