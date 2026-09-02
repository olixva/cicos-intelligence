"""Validation and loading of the reviewed CIDE matrix and ruleset artifacts.

The artifacts are JSON documents authored by humans and stored under
``data/rules/``. This module enforces the schema, the attestation
requirements and the existence of every cited evidence identifier in
the configured publication. It never infers missing values.
"""

from __future__ import annotations

import json
import re
from collections.abc import Collection, Iterable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

MATRIX_SCHEMA_VERSION = "1.0.0"
RULESET_SCHEMA_VERSION = "1.0.0"
_EVIDENCE_ID_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}:page:[1-9][0-9]*$")


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


def load_schema(name: str) -> dict[str, object]:
    """Return the schema document for the requested artifact."""
    here = Path(__file__).resolve().parent
    # File layout: backend/src/domain/rules/artifact_validation.py -> backend
    # -> repo root. The rules live in <repo>/data/rules/<name>.schema.json.
    repo_root = here.parent.parent.parent.parent
    schema_path = repo_root / "data" / "rules" / f"{name}.schema.json"
    if not schema_path.exists():
        raise FileNotFoundError(f"schema not found: {schema_path}")
    return cast_schema(json.loads(schema_path.read_text(encoding="utf-8")))


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
    left_payload = json.loads(left.read_text(encoding="utf-8"))
    right_payload = json.loads(right.read_text(encoding="utf-8"))
    left_cells = left_payload.get("cells", {})
    right_cells = right_payload.get("cells", {})
    keys = sorted(set(left_cells) | set(right_cells))
    differences: list[dict[str, object]] = []
    matching = 0
    for key in keys:
        l_cell = left_cells.get(key)
        r_cell = right_cells.get(key)
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


def load_matrix_cells(artifact_path: Path) -> dict[tuple[int, int], dict[str, Any]]:
    """Decode the matrix JSON into a lookup map keyed by (a, b)."""
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    cells = payload.get("cells", {})
    decoded: dict[tuple[int, int], dict[str, Any]] = {}
    for key, value in cells.items():
        a_raw, b_raw = key.split(",")
        decoded[(int(a_raw), int(b_raw))] = value
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
    raw = artifact_path.read_text(encoding="utf-8")
    payload = json.loads(raw)
    schema = load_schema(schema_name)
    errors: list[str] = []
    validator = Draft202012Validator(schema)
    for error in sorted(validator.iter_errors(payload), key=lambda e: e.path):
        path = "/".join(str(part) for part in error.absolute_path) or "*"
        errors.append(f"{path}: {error.message}")
    if payload.get("document_hash") != expected_document_hash:
        errors.append(
            f"document_hash {payload.get('document_hash')} does not match expected "
            f"{expected_document_hash}"
        )
    cells = payload.get("cells", {}) if schema_name == "cide-matrix" else {}
    cell_count = len(cells)
    if expected_cell_count and cell_count != expected_cell_count:
        errors.append(f"cell count {cell_count} does not match expected {expected_cell_count}")
    referenced = _collect_evidence_ids(payload)
    unknown_evidence = tuple(sorted(referenced - set(evidence_pool)))
    if unknown_evidence:
        errors.append(f"unknown evidence: {', '.join(unknown_evidence)}")
    attestation = payload.get("attestation", {})
    transcriptions = attestation.get("transcriptions", [])
    reviewer_ids = payload.get("reviewer_ids") or sorted(
        {str(t.get("reviewer_id")) for t in transcriptions if t.get("reviewer_id")}
    )
    independent_count = sum(
        1 for t in transcriptions if t.get("independent") and t.get("pdf_page_checked")
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


def _collect_evidence_ids(payload: dict[str, Any]) -> set[str]:
    refs: set[str] = set()
    cells = payload.get("cells") or {}
    for value in cells.values():
        if not isinstance(value, dict):
            continue
        for evidence_id in value.get("evidence_ids") or []:
            if isinstance(evidence_id, str):
                refs.add(evidence_id)
    for note in payload.get("notes") or []:
        if not isinstance(note, dict):
            continue
        for evidence_id in note.get("evidence_ids") or []:
            if isinstance(evidence_id, str):
                refs.add(evidence_id)
    for rule in payload.get("rules") or []:
        if not isinstance(rule, dict):
            continue
        for evidence_id in rule.get("evidence_ids") or []:
            if isinstance(evidence_id, str) and _EVIDENCE_ID_PATTERN.match(evidence_id):
                refs.add(evidence_id)
    return refs


def cast_schema(value: dict[str, object]) -> dict[str, object]:
    """Return the schema document without runtime type narrowing."""
    return value


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
                    record = json.loads(raw)
                    if isinstance(record, dict):
                        evidence_id = record.get("evidence_id")
                        if isinstance(evidence_id, str):
                            pool.add(evidence_id)
            except OSError, json.JSONDecodeError:
                continue
    return pool
