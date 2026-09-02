"""Load and validate the signed rules artifacts at composition time.

The claim workflow may only decide from artifacts a human attested. Loading
them is therefore a startup decision with two outcomes and no third: either
both artifacts validate and the workflow can apply them, or the process
refuses to start. Degrading silently to "no rules" would let a demo present
an unsupported conclusion, which is the failure mode this project exists to
avoid.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from domain.models.claim import MatrixCell
from domain.rules.artifact_validation import (
    JsonObject,
    RulesArtifactError,
    evidence_pool_from_publications,
    load_json_object,
    load_matrix_cells,
    validate_cide_matrix,
    validate_ruleset,
)
from domain.rules.ruleset import LoadedRule

DEFAULT_DOCUMENT_HASH = "b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344"
MATRIX_FILENAME = "cide-matrix.v1.json"
RULESET_FILENAME = "ruleset.v1.json"


class RulesArtifactsUnavailable(RuntimeError):
    """Raised when the signed artifacts are missing or fail their attestation."""


@dataclass(frozen=True, slots=True)
class RulesArtifacts:
    """The reviewed corpus the claim workflow is allowed to apply."""

    rules: tuple[LoadedRule, ...]
    matrix_cells: dict[tuple[int, int], MatrixCell]
    row_labels: tuple[str, ...]
    column_labels: tuple[str, ...]


def load_rules_artifacts(
    rules_root: Path,
    *,
    expected_document_hash: str | None = None,
    evidence_roots: tuple[Path, ...] | None = None,
) -> RulesArtifacts:
    """Validate both artifacts and decode them, or raise."""
    document_hash = expected_document_hash or os.environ.get(
        "ALLIANZ_DOCUMENT_HASH", DEFAULT_DOCUMENT_HASH
    )
    matrix_path = rules_root / MATRIX_FILENAME
    ruleset_path = rules_root / RULESET_FILENAME
    for path, label in ((matrix_path, "matrix"), (ruleset_path, "ruleset")):
        if not path.exists():
            raise RulesArtifactsUnavailable(f"{label} artifact not found: {path}")

    roots = evidence_roots or (rules_root.parent / "extractions",)
    pool = evidence_pool_from_publications(roots)

    for path, label, validate in (
        (matrix_path, "matrix", validate_cide_matrix),
        (ruleset_path, "ruleset", validate_ruleset),
    ):
        try:
            report = validate(path, expected_document_hash=document_hash, evidence_pool=pool)
        except RulesArtifactError as error:
            raise RulesArtifactsUnavailable(f"{label} artifact is invalid: {error}") from error
        if report.errors:
            raise RulesArtifactsUnavailable(
                f"{label} artifact is invalid: {'; '.join(report.errors)}"
            )
        if not report.attestation_complete:
            raise RulesArtifactsUnavailable(
                f"{label} artifact has an incomplete attestation and must not drive decisions"
            )

    matrix_payload = load_json_object(matrix_path)
    cells = {
        position: MatrixCell(
            a=position[0],
            b=position[1],
            outcome=str(cell["outcome"]),
            evidence_ids=_string_values(cell.get("evidence_ids")),
        )
        for position, cell in load_matrix_cells(matrix_path).items()
    }
    return RulesArtifacts(
        rules=tuple(
            _rule(raw) for raw in _object_list(load_json_object(ruleset_path).get("rules"))
        ),
        matrix_cells=cells,
        row_labels=_string_values(matrix_payload.get("row_labels")),
        column_labels=_string_values(matrix_payload.get("column_labels")),
    )


def _rule(raw: JsonObject) -> LoadedRule:
    applies_when = raw.get("applies_when")
    return LoadedRule(
        rule_id=str(raw["rule_id"]),
        kind=str(raw["kind"]),
        description=str(raw["description"]),
        prerequisites=_string_values(raw.get("prerequisites")),
        outcome=str(raw["outcome"]) if raw.get("outcome") else None,
        evidence_ids=_string_values(raw.get("evidence_ids")),
        applies_when=cast(dict[str, object], applies_when)
        if isinstance(applies_when, dict)
        else None,
        convention=_convention(raw.get("convention")),
    )


def _convention(value: object) -> Literal["CIDE", "ASCIDE"] | None:
    """Only the two conventions the manual defines; anything else stays unknown."""
    if value == "CIDE" or value == "ASCIDE":
        return cast(Literal["CIDE", "ASCIDE"], value)
    return None


def _object_list(value: object) -> tuple[JsonObject, ...]:
    if not isinstance(value, list):
        raise RulesArtifactsUnavailable("ruleset rules must be a JSON array")
    objects: list[JsonObject] = []
    for raw_item in cast(list[object], value):
        if not isinstance(raw_item, dict):
            raise RulesArtifactsUnavailable("ruleset rules must contain JSON objects")
        item = cast(dict[object, object], raw_item)
        if not all(isinstance(key, str) for key in item):
            raise RulesArtifactsUnavailable("ruleset rules must contain JSON objects")
        objects.append(cast(JsonObject, item))
    return tuple(objects)


def _string_values(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in cast(list[object], value) if isinstance(item, str))
