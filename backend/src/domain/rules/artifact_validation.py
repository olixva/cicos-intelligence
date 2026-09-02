"""Validation and loading of the reviewed CIDE matrix and ruleset artifacts.

The artifacts are JSON documents authored by humans and stored under
``data/rules/``. This module enforces the schema, the attestation
requirements and the existence of every cited evidence identifier in
the configured publication. It never infers missing values.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Collection, Iterable, Iterator
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import cast

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

MATRIX_SCHEMA_VERSION = "1.0.0"
RULESET_SCHEMA_VERSION = "1.0.0"
_EVIDENCE_ID_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}:page:[1-9][0-9]*$")
type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]
type JsonArray = list[JsonValue]


class RulesArtifactError(ValueError):
    """Raised when a rules artifact fails schema, attestation or evidence checks."""


@dataclass(frozen=True)
class RulesValidationReport:
    """Structured outcome of one validate call so the CLI can serialize it."""

    schema_version: str
    artifact_path: str
    cell_count: int
    expected_cell_count: int
    reviewer_count: int
    attestation_complete: bool
    evidence_pool_size: int
    unknown_evidence: tuple[str, ...]
    errors: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors


def load_schema(name: str) -> JsonObject:
    """Return the schema document for the requested artifact."""
    here = Path(__file__).resolve().parent
    # File layout: backend/src/domain/rules/artifact_validation.py -> backend
    # -> repo root. The rules live in <repo>/data/rules/<name>.schema.json.
    repo_root = here.parent.parent.parent.parent
    schema_path = repo_root / "data" / "rules" / f"{name}.schema.json"
    if not schema_path.exists():
        raise FileNotFoundError(f"schema not found: {schema_path}")
    return load_json_object(schema_path)


def validate_cide_matrix(
    artifact_path: Path,
    *,
    expected_document_hash: str,
    evidence_pool: Collection[str],
) -> RulesValidationReport:
    """Validate a cide-matrix.v1.json artifact against the schema and attestation rules."""
    return _validate_rules_artifact(
        artifact_path=artifact_path,
        schema_name="cide-matrix",
        expected_document_hash=expected_document_hash,
        evidence_pool=evidence_pool,
        expected_cell_count=324,
    )


def validate_ruleset(
    artifact_path: Path,
    *,
    expected_document_hash: str,
    evidence_pool: Collection[str],
) -> RulesValidationReport:
    """Validate a ruleset.v1.json artifact against the schema and attestation rules."""
    return _validate_rules_artifact(
        artifact_path=artifact_path,
        schema_name="ruleset",
        expected_document_hash=expected_document_hash,
        evidence_pool=evidence_pool,
        expected_cell_count=0,
    )


def compare_transcriptions(left: Path, right: Path) -> dict[str, object]:
    """Return the symmetric difference of two matrix transcriptions without adjudication."""
    left_payload = load_json_object(left)
    right_payload = load_json_object(right)
    left_cells = _json_object(left_payload.get("cells")) or {}
    right_cells = _json_object(right_payload.get("cells")) or {}
    keys = sorted(set(left_cells) | set(right_cells))
    differences: list[dict[str, object]] = []
    matching = 0
    for key in keys:
        l_cell = _json_object(left_cells.get(key))
        r_cell = _json_object(right_cells.get(key))
        if l_cell is None or r_cell is None:
            differences.append(
                {
                    "cell": key,
                    "missing_in": "left" if l_cell is None else "right",
                }
            )
            continue
        l_outcome = l_cell.get("outcome")
        r_outcome = r_cell.get("outcome")
        if l_outcome == r_outcome:
            matching += 1
        else:
            differences.append(
                {
                    "cell": key,
                    "left_outcome": l_outcome,
                    "right_outcome": r_outcome,
                }
            )
    return {
        "left_path": str(left),
        "right_path": str(right),
        "compared_cells": len(keys),
        "matching_cells": matching,
        "differences": differences,
    }


def load_matrix_cells(artifact_path: Path) -> dict[tuple[int, int], JsonObject]:
    """Decode the matrix JSON into a lookup map keyed by (a, b)."""
    payload = load_json_object(artifact_path)
    cells = _json_object(payload.get("cells")) or {}
    decoded: dict[tuple[int, int], JsonObject] = {}
    for key, value in cells.items():
        a_raw, b_raw = key.split(",")
        cell = _json_object(value)
        if cell is None:
            raise RulesArtifactError(f"matrix cell {key} is not a JSON object")
        decoded[(int(a_raw), int(b_raw))] = cell
    return decoded


def _validate_rules_artifact(
    *,
    artifact_path: Path,
    schema_name: str,
    expected_document_hash: str,
    evidence_pool: Collection[str],
    expected_cell_count: int,
) -> RulesValidationReport:
    if not artifact_path.exists():
        raise RulesArtifactError(f"artifact not found: {artifact_path}")
    payload = load_json_object(artifact_path)
    schema = load_schema(schema_name)
    errors: list[str] = []
    validator = Draft202012Validator(schema)
    iter_errors = cast(
        Callable[[JsonObject], Iterator[ValidationError]],
        object.__getattribute__(validator, "iter_errors"),
    )
    validation_errors = iter_errors(payload)
    for error in sorted(validation_errors, key=lambda error: error.path):
        path = "/".join(str(part) for part in error.absolute_path) or "*"
        errors.append(f"{path}: {error.message}")
    if payload.get("document_hash") != expected_document_hash:
        errors.append(
            f"document_hash {payload.get('document_hash')} does not match expected "
            f"{expected_document_hash}"
        )
    cells = (_json_object(payload.get("cells")) or {}) if schema_name == "cide-matrix" else {}
    cell_count = len(cells)
    if expected_cell_count and cell_count != expected_cell_count:
        errors.append(f"cell count {cell_count} does not match expected {expected_cell_count}")
    referenced = _collect_evidence_ids(payload)
    unknown_evidence = tuple(sorted(referenced - set(evidence_pool)))
    if unknown_evidence:
        errors.append(f"unknown evidence: {', '.join(unknown_evidence)}")
    attestation = _json_object(payload.get("attestation")) or {}
    transcriptions = _json_array(attestation.get("transcriptions")) or []
    reviewer_ids = _string_values(payload.get("reviewer_ids")) or sorted(
        {
            reviewer_id
            for transcription in transcriptions
            if (entry := _json_object(transcription)) is not None
            and isinstance((reviewer_id := entry.get("reviewer_id")), str)
            and reviewer_id
        }
    )
    independent_count = sum(
        1
        for transcription in transcriptions
        if (entry := _json_object(transcription)) is not None
        and entry.get("independent") is True
        and entry.get("pdf_page_checked") is True
    )
    attestation_complete = (
        independent_count >= 2
        and bool(attestation.get("divergence_resolution"))
        and bool(attestation.get("signed_by"))
    )
    if independent_count < 2:
        errors.append(
            f"attestation has {independent_count} independent transcription(s); need at least 2"
        )
    if not attestation.get("divergence_resolution"):
        errors.append("attestation.divergence_resolution is empty")
    if not attestation.get("signed_by"):
        errors.append("attestation.signed_by is empty")
    return RulesValidationReport(
        schema_version=str(payload.get("schema_version", "")),
        artifact_path=str(artifact_path),
        cell_count=cell_count,
        expected_cell_count=expected_cell_count,
        reviewer_count=len(reviewer_ids),
        attestation_complete=attestation_complete,
        evidence_pool_size=len(set(evidence_pool)),
        unknown_evidence=unknown_evidence,
        errors=tuple(errors),
    )


def _collect_evidence_ids(payload: JsonObject) -> set[str]:
    refs: set[str] = set()
    cells = _json_object(payload.get("cells")) or {}
    for value in cells.values():
        cell = _json_object(value)
        if cell is None:
            continue
        for evidence_id in _json_array(cell.get("evidence_ids")) or []:
            if isinstance(evidence_id, str):
                refs.add(evidence_id)
    for raw_note in _json_array(payload.get("notes")) or []:
        note = _json_object(raw_note)
        if note is None:
            continue
        for evidence_id in _json_array(note.get("evidence_ids")) or []:
            if isinstance(evidence_id, str):
                refs.add(evidence_id)
    for raw_rule in _json_array(payload.get("rules")) or []:
        rule = _json_object(raw_rule)
        if rule is None:
            continue
        for evidence_id in _json_array(rule.get("evidence_ids")) or []:
            if isinstance(evidence_id, str) and _EVIDENCE_ID_PATTERN.match(evidence_id):
                refs.add(evidence_id)
    return refs


def load_json_object(path: Path) -> JsonObject:
    """Decode a JSON object while rejecting arrays and scalar documents early."""
    value: object = json.loads(path.read_text(encoding="utf-8"))
    parsed = _json_object(value)
    if parsed is None:
        raise RulesArtifactError(f"{path} must contain a JSON object")
    return parsed


def _json_object(value: object) -> JsonObject | None:
    if not isinstance(value, dict):
        return None
    mapping = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in mapping):
        return None
    return cast(JsonObject, mapping)


def _json_array(value: object) -> JsonArray | None:
    if not isinstance(value, list):
        return None
    return cast(JsonArray, value)


def _string_values(value: object) -> list[str]:
    values = _json_array(value)
    if values is None:
        return []
    return [item for item in values if isinstance(item, str)]


def transcription_sha256(transcription_path: Path) -> str:
    """Compute the SHA-256 of a raw transcription JSON for attestation."""
    return sha256(transcription_path.read_bytes()).hexdigest()


def evidence_pool_from_publications(evidence_roots: Iterable[Path]) -> set[str]:
    """Collect every evidence ID present under the configured publication roots."""
    pool: set[str] = set()
    for root in evidence_roots:
        if not root.exists():
            continue
        for pages in root.glob("*/*/pages.jsonl"):
            try:
                for raw in pages.read_text(encoding="utf-8").splitlines():
                    if not raw.strip():
                        continue
                    record: object = json.loads(raw)
                    if (entry := _json_object(record)) is not None:
                        evidence_id = entry.get("evidence_id")
                        if isinstance(evidence_id, str):
                            pool.add(evidence_id)
            except OSError, json.JSONDecodeError:
                continue
    return pool
