"""Deterministic validation and hashing for frozen golden-set releases."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Collection, Sequence
from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from infrastructure.adapters.outbound.evaluation.golden_schema import (
    SCHEMA_VERSION,
    GoldenDatasetItem,
    canonical_schema_bytes,
)


class ReleaseManifest(BaseModel):
    """Hash-bound identity for one canonical dataset snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str
    dataset_name: str
    dataset_version: str
    item_count: int
    case_ids: tuple[str, ...]
    partition_counts: tuple[tuple[Literal["development", "holdout"], int], ...]
    content_sha256: str
    schema_sha256: str

    @field_validator("dataset_name", "dataset_version")
    @classmethod
    def validate_identity(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("release identity must be nonempty")
        return value


def check_family_splits(assignments: Sequence[tuple[str, str]]) -> None:
    """Reject a family assigned to both development and holdout."""

    seen: dict[str, str] = {}
    for family_id, partition in assignments:
        if not family_id.strip() or partition not in ("development", "holdout"):
            raise ValueError("family assignment is invalid")
        if family_id in seen and seen[family_id] != partition:
            raise ValueError(f"family {family_id} crosses partitions")
        seen[family_id] = partition


def validate_release(
    items: Sequence[dict[str, object]], *, existing_evidence_ids: Collection[str]
) -> tuple[GoldenDatasetItem, ...]:
    """Validate native item fields, review completion, evidence, and split isolation."""

    if not items:
        raise ValueError("golden release cannot be empty")
    validated: list[GoldenDatasetItem] = []
    for index, item in enumerate(items):
        try:
            validated.append(GoldenDatasetItem.model_validate(item))
        except (ValidationError, ValueError) as error:
            raise ValueError(f"golden item schema is invalid at index {index}") from error

    case_ids = tuple(item.metadata.case_id for item in validated)
    duplicates = sorted(case_id for case_id, count in Counter(case_ids).items() if count > 1)
    if duplicates:
        raise ValueError(f"duplicate case identifiers: {', '.join(duplicates)}")

    check_family_splits(
        tuple((item.metadata.family_id, item.metadata.partition) for item in validated)
    )
    known_evidence = set(existing_evidence_ids)
    for item in validated:
        metadata = item.metadata
        review = metadata.review
        if metadata.review_status != "adjudicated":
            raise ValueError(f"case {metadata.case_id} has incomplete review status")
        if (
            not (
                review.independent_resolution_checked
                and review.evidence_checked
                and review.adversarial_checked
            )
            or review.open_discrepancies
        ):
            raise ValueError(f"case {metadata.case_id} has incomplete review checks")
        referenced = {
            evidence_id
            for requirement in item.expected_output.evidence_requirements
            for bundle in requirement.any_of
            for evidence_id in bundle.all_of
        }
        unknown = sorted(referenced - known_evidence)
        if unknown:
            raise ValueError(
                f"case {metadata.case_id} references unknown evidence: {', '.join(unknown)}"
            )
    return tuple(validated)


def canonical_jsonl(
    items: Sequence[dict[str, object]], *, existing_evidence_ids: Collection[str]
) -> bytes:
    """Return the validated snapshot bytes whose exact order is part of release identity."""

    validated = validate_release(items, existing_evidence_ids=existing_evidence_ids)
    lines = (
        json.dumps(
            item.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        for item in validated
    )
    return ("\n".join(lines) + "\n").encode()


def build_release_manifest(
    *,
    dataset_name: str,
    dataset_version: str,
    items: Sequence[dict[str, object]],
    schema: bytes,
    existing_evidence_ids: Collection[str],
) -> ReleaseManifest:
    """Bind canonical item bytes and the external schema document to one release identity."""

    if schema != canonical_schema_bytes():
        raise ValueError("golden schema document is not the canonical schema")
    validated = validate_release(items, existing_evidence_ids=existing_evidence_ids)
    content = canonical_jsonl(items, existing_evidence_ids=existing_evidence_ids)
    counts = Counter(item.metadata.partition for item in validated)
    return ReleaseManifest(
        schema_version=SCHEMA_VERSION,
        dataset_name=dataset_name,
        dataset_version=dataset_version,
        item_count=len(validated),
        case_ids=tuple(item.metadata.case_id for item in validated),
        partition_counts=(("development", counts["development"]), ("holdout", counts["holdout"])),
        content_sha256=sha256(content).hexdigest(),
        schema_sha256=sha256(schema).hexdigest(),
    )
