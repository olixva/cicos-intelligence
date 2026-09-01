"""Versioned reference schema layered over native Langfuse item fields."""

from __future__ import annotations

import json
import re
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator

SCHEMA_VERSION = "1.0.0"
_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*")

type Intent = Literal["question", "claim", "clarification_required"]


class _GoldenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class GoldenInput(_GoldenModel):
    """Only fields that may cross the evaluation boundary into the system."""

    text: str
    language: Literal["es", "en"]
    clarifications: tuple[str, ...] = ()

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("input text must be nonempty")
        return value

    @field_validator("clarifications")
    @classmethod
    def validate_clarifications(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item.strip() for item in value) or len(set(value)) != len(value):
            raise ValueError("clarifications must be nonempty and unique")
        return value


class ExpectedDecisions(_GoldenModel):
    """Closed reference decisions shared by question, routing, and claim cases."""

    intent: Intent
    answer_status: (
        Literal["answered", "partial", "insufficient_evidence", "out_of_scope"] | None
    ) = None
    applicability: Literal["applicable", "not_applicable", "undetermined"] | None = None
    convention: Literal["CIDE", "ASCIDE"] | None = None
    claim_decision: Literal["resolved", "conditional", "undetermined", "not_assessed"] | None = None


class AnswerRequirement(_GoldenModel):
    requirement_id: str
    description: str

    @field_validator("requirement_id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return _identifier("requirement_id", value)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        return _nonempty("requirement description", value)


class AcceptableAlternative(_GoldenModel):
    alternative_id: str
    description: str
    satisfies: tuple[str, ...] = Field(min_length=1)

    @field_validator("alternative_id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return _identifier("alternative_id", value)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        return _nonempty("alternative description", value)

    @field_validator("satisfies")
    @classmethod
    def validate_satisfies(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _unique_identifiers("alternative requirement", value)


class EvidenceBundle(_GoldenModel):
    """Every ID in ``all_of`` is required together (logical AND)."""

    bundle_id: str
    all_of: tuple[str, ...] = Field(min_length=1)

    @field_validator("bundle_id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return _identifier("bundle_id", value)

    @field_validator("all_of")
    @classmethod
    def validate_all_of(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _unique_nonempty("evidence identifier", value)


class EvidenceRequirement(_GoldenModel):
    """Any complete bundle in ``any_of`` is acceptable (logical OR)."""

    requirement_id: str
    any_of: tuple[EvidenceBundle, ...] = Field(min_length=1)

    @field_validator("requirement_id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return _identifier("requirement_id", value)

    @model_validator(mode="after")
    def validate_unique_bundles(self) -> Self:
        bundle_ids = tuple(bundle.bundle_id for bundle in self.any_of)
        if len(set(bundle_ids)) != len(bundle_ids):
            raise ValueError("evidence bundle identifiers must be unique")
        return self


class GoldenExpectedOutput(_GoldenModel):
    reference: str
    decisions: ExpectedDecisions
    requirements: tuple[AnswerRequirement, ...] = Field(min_length=1)
    acceptable_alternatives: tuple[AcceptableAlternative, ...]
    forbidden_facts: tuple[str, ...]
    evidence_requirements: tuple[EvidenceRequirement, ...]

    @field_validator("reference")
    @classmethod
    def validate_reference(cls, value: str) -> str:
        return _nonempty("reference", value)

    @field_validator("forbidden_facts")
    @classmethod
    def validate_forbidden_facts(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _unique_nonempty("forbidden fact", value)

    @model_validator(mode="after")
    def validate_requirement_links(self) -> Self:
        requirement_ids = tuple(item.requirement_id for item in self.requirements)
        if len(set(requirement_ids)) != len(requirement_ids):
            raise ValueError("answer requirement identifiers must be unique")
        known = set(requirement_ids)
        evidence_ids = tuple(item.requirement_id for item in self.evidence_requirements)
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("evidence requirement identifiers must be unique")
        unknown_links = set(evidence_ids) - known
        unknown_links.update(
            requirement_id
            for alternative in self.acceptable_alternatives
            for requirement_id in alternative.satisfies
            if requirement_id not in known
        )
        if unknown_links:
            raise ValueError(
                f"unknown answer requirement links: {', '.join(sorted(unknown_links))}"
            )
        alternative_ids = tuple(item.alternative_id for item in self.acceptable_alternatives)
        if len(set(alternative_ids)) != len(alternative_ids):
            raise ValueError("acceptable alternative identifiers must be unique")
        return self


class Provenance(_GoldenModel):
    kind: Literal[
        "interview_example",
        "manual_derived",
        "adversarial",
        "synthetic",
        "technical_fixture",
    ]
    source_ids: tuple[str, ...] = Field(min_length=1)

    @field_validator("source_ids")
    @classmethod
    def validate_sources(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _unique_nonempty("provenance source", value)


class ReviewRecord(_GoldenModel):
    reviewer_ids: tuple[str, ...] = Field(min_length=1)
    independent_resolution_checked: StrictBool
    evidence_checked: StrictBool
    adversarial_checked: StrictBool
    adjudication_note: str
    open_discrepancies: tuple[str, ...]

    @field_validator("reviewer_ids")
    @classmethod
    def validate_reviewers(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _unique_nonempty("reviewer identifier", value)

    @field_validator("adjudication_note")
    @classmethod
    def validate_note(cls, value: str) -> str:
        return _nonempty("adjudication note", value)

    @field_validator("open_discrepancies")
    @classmethod
    def validate_discrepancies(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _unique_nonempty("open discrepancy", value)


class GoldenMetadata(_GoldenModel):
    case_id: str
    family_id: str
    partition: Literal["development", "holdout"]
    review_status: Literal["candidate", "in_review", "adjudicated", "quarantined"]
    provenance: Provenance
    language: Literal["es", "en"]
    expected_intent: Intent
    review: ReviewRecord

    @field_validator("case_id", "family_id")
    @classmethod
    def validate_ids(cls, value: str) -> str:
        return _identifier("metadata identifier", value)


class GoldenDatasetItem(_GoldenModel):
    """The three native Langfuse item fields with project-specific nested references."""

    input: GoldenInput
    expected_output: GoldenExpectedOutput
    metadata: GoldenMetadata

    @model_validator(mode="after")
    def validate_cross_field_labels(self) -> Self:
        if self.input.language != self.metadata.language:
            raise ValueError("input and metadata languages differ")
        if self.expected_output.decisions.intent != self.metadata.expected_intent:
            raise ValueError("expected intent differs between reference and metadata")
        return self


def golden_json_schema() -> dict[str, object]:
    """Export the versioned JSON Schema without duplicating Langfuse dataset models."""

    schema = GoldenDatasetItem.model_json_schema()
    schema["$id"] = f"https://cicos-intelligence.local/schemas/golden/{SCHEMA_VERSION}"
    schema["x-schema-version"] = SCHEMA_VERSION
    return schema


def canonical_schema_bytes() -> bytes:
    """Return the exact schema artifact a release is allowed to bind."""
    return (
        json.dumps(golden_json_schema(), ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode()


def _identifier(name: str, value: str) -> str:
    if _ID_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{name} is invalid")
    return value


def _nonempty(name: str, value: str) -> str:
    if not value.strip():
        raise ValueError(f"{name} must be nonempty")
    return value


def _unique_identifiers(name: str, values: tuple[str, ...]) -> tuple[str, ...]:
    for value in values:
        _identifier(name, value)
    if len(set(values)) != len(values):
        raise ValueError(f"{name}s must be unique")
    return values


def _unique_nonempty(name: str, values: tuple[str, ...]) -> tuple[str, ...]:
    if any(not value.strip() for value in values) or len(set(values)) != len(values):
        raise ValueError(f"{name}s must be nonempty and unique")
    return values
