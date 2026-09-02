"""Tests for the rules artifact validator.

These tests build a synthetic matrix and ruleset that pass every
required check, plus a couple of negative fixtures, to assert that the
validator catches every documented gap.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from domain.rules.artifact_validation import (
    RulesArtifactError,
    compare_transcriptions,
    evidence_pool_from_publications,
    load_schema,
    transcription_sha256,
    validate_cide_matrix,
    validate_ruleset,
)


def _evidence_ids(*numbers: int) -> tuple[str, ...]:
    document_hash = "b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344"
    return tuple(f"sha256:{document_hash}:page:{n}" for n in numbers)


DOCUMENT_HASH = "b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344"


def _complete_matrix(document_hash: str) -> dict[str, object]:
    cells: dict[str, dict[str, object]] = {}
    for a in range(1, 19):
        for b in range(1, 19):
            key = f"{a},{b}"
            cells[key] = {
                "a": a,
                "b": b,
                "outcome": "no_convention",
                "normalized_outcome": "no_convention",
                "evidence_ids": list(_evidence_ids(101)),
                "reviewer_id": "reviewer-1",
            }
    return {
        "schema_version": "1.0.0",
        "document_hash": document_hash,
        "pdf_page": 101,
        "orientation": "A-row-B-column",
        "row_labels": [f"A{i}" for i in range(1, 19)],
        "column_labels": [f"B{j}" for j in range(1, 19)],
        "cells": cells,
        "notes": [],
        "reviewer_ids": ["reviewer-1", "reviewer-2"],
        "attestation": {
            "transcriptions": [
                {
                    "reviewer_id": "reviewer-1",
                    "independent": True,
                    "pdf_page_checked": True,
                    "transcription_sha256": "a" * 64,
                },
                {
                    "reviewer_id": "reviewer-2",
                    "independent": True,
                    "pdf_page_checked": True,
                    "transcription_sha256": "b" * 64,
                },
            ],
            "divergence_resolution": "No divergences after PDF review.",
            "signed_by": ["lead-reviewer"],
            "signed_at": "2026-09-02T00:00:00Z",
        },
    }


def _complete_ruleset(document_hash: str) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "document_hash": document_hash,
        "rules": [
            {
                "rule_id": "applicability-two-vehicles",
                "kind": "applicability",
                "description": "Convenios require exactly two vehicles.",
                "prerequisites": [],
                "outcome": "not_applicable",
                "evidence_ids": list(_evidence_ids(20)),
                "reviewer_id": "reviewer-1",
            }
        ],
        "attestation": {
            "transcriptions": [
                {
                    "reviewer_id": "reviewer-1",
                    "independent": True,
                    "pdf_page_checked": True,
                    "transcription_sha256": "c" * 64,
                },
                {
                    "reviewer_id": "reviewer-2",
                    "independent": True,
                    "pdf_page_checked": True,
                    "transcription_sha256": "d" * 64,
                },
            ],
            "divergence_resolution": "Both reviewers agreed.",
            "signed_by": ["lead-reviewer"],
            "signed_at": "2026-09-02T00:00:00Z",
        },
    }


def test_load_schema_returns_canonical_documents() -> None:
    """Each schema must load with the expected title."""
    matrix_schema = load_schema("cide-matrix")
    ruleset_schema = load_schema("ruleset")
    assert matrix_schema["title"].startswith("Allianz RAG — CIDE matrix")
    assert ruleset_schema["title"].startswith("Allianz RAG — Ruleset")


def test_validate_cide_matrix_accepts_a_complete_artifact(tmp_path: Path) -> None:
    """A complete matrix with full attestation must validate without errors."""
    document_hash = "b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344"
    payload = _complete_matrix(document_hash)
    matrix_path = tmp_path / "cide-matrix.v1.json"
    matrix_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    report = validate_cide_matrix(
        matrix_path, expected_document_hash=document_hash, evidence_pool=set(_evidence_ids(101))
    )
    assert report.ok, report.errors
    assert report.cell_count == 324
    assert report.attestation_complete


def test_validate_cide_matrix_rejects_short_attestation(tmp_path: Path) -> None:
    """An attestation with a single reviewer must be rejected."""
    document_hash = "b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344"
    payload = _complete_matrix(document_hash)
    payload["attestation"]["transcriptions"] = payload["attestation"]["transcriptions"][:1]
    matrix_path = tmp_path / "cide-matrix.v1.json"
    matrix_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    report = validate_cide_matrix(
        matrix_path, expected_document_hash=document_hash, evidence_pool=set(_evidence_ids(101))
    )
    assert not report.ok
    assert any("independent transcription" in err for err in report.errors)


def test_validate_cide_matrix_rejects_unknown_evidence(tmp_path: Path) -> None:
    """Cells citing evidence not in the publication pool must be flagged."""
    document_hash = DOCUMENT_HASH
    payload = _complete_matrix(document_hash)
    payload["cells"]["1,1"]["evidence_ids"] = [f"sha256:{document_hash}:page:1"]
    matrix_path = tmp_path / "cide-matrix.v1.json"
    matrix_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    report = validate_cide_matrix(
        matrix_path, expected_document_hash=document_hash, evidence_pool=set(_evidence_ids(101))
    )
    assert not report.ok
    assert any("unknown evidence" in err for err in report.errors)


def test_validate_ruleset_accepts_a_complete_artifact(tmp_path: Path) -> None:
    """A ruleset with full attestation must validate."""
    document_hash = "b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344"
    payload = _complete_ruleset(document_hash)
    ruleset_path = tmp_path / "ruleset.v1.json"
    ruleset_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    report = validate_ruleset(
        ruleset_path,
        expected_document_hash=document_hash,
        evidence_pool=set(_evidence_ids(20)),
    )
    assert report.ok, report.errors


def test_validate_cide_matrix_rejects_document_hash_mismatch(tmp_path: Path) -> None:
    """The artifact hash must match the configured document hash."""
    payload = _complete_matrix("f" * 64)
    matrix_path = tmp_path / "cide-matrix.v1.json"
    matrix_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    expected_hash = "b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344"
    report = validate_cide_matrix(
        matrix_path, expected_document_hash=expected_hash, evidence_pool=set(_evidence_ids(101))
    )
    assert not report.ok
    assert any("document_hash" in err for err in report.errors)


def test_compare_transcriptions_reports_only_differences(tmp_path: Path) -> None:
    """compare-transcriptions must return divergences without touching the artifact."""
    left_payload = _complete_matrix(DOCUMENT_HASH)
    right_payload = _complete_matrix(DOCUMENT_HASH)
    right_payload["cells"]["1,1"]["outcome"] = "A_full"
    left = tmp_path / "left.json"
    right = tmp_path / "right.json"
    left.write_text(json.dumps(left_payload), encoding="utf-8")
    right.write_text(json.dumps(right_payload), encoding="utf-8")
    report = compare_transcriptions(left, right)
    assert report["compared_cells"] == 324
    differences = report["differences"]
    assert any(diff.get("cell") == "1,1" for diff in differences)


def test_transcription_sha256_matches_independent_bytes(tmp_path: Path) -> None:
    """The attestation hash must come from the raw transcription JSON."""
    payload = _complete_matrix("b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344")
    path = tmp_path / "raw.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    assert transcription_sha256(path) == transcription_sha256(path)


def test_validate_cide_matrix_missing_artifact_raises(tmp_path: Path) -> None:
    """Pointing at a missing file must raise RulesArtifactError."""
    with pytest.raises(RulesArtifactError):
        validate_cide_matrix(
            tmp_path / "missing.json",
            expected_document_hash="b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344",
            evidence_pool=set(),
        )


def test_validate_ruleset_rejects_a_json_array(tmp_path: Path) -> None:
    """A non-object artifact must fail at the JSON boundary, not during validation."""
    path = tmp_path / "ruleset.v1.json"
    path.write_text("[]", encoding="utf-8")

    with pytest.raises(RulesArtifactError, match="JSON object"):
        validate_ruleset(path, expected_document_hash=DOCUMENT_HASH, evidence_pool=set())


def test_evidence_pool_from_publications_reads_pages_jsonl(tmp_path: Path) -> None:
    """The helper must aggregate evidence IDs from every publication directory."""
    document_hash = "b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344"
    parser_dir = tmp_path / document_hash / "pypdf-6.16.2"
    parser_dir.mkdir(parents=True)
    (parser_dir / "manifest.json").write_text(
        json.dumps(
            {
                "document_id": f"sha256:{document_hash}",
                "sha256": document_hash,
                "filename": f"{document_hash}.pdf",
                "page_count": 1,
            }
        ),
        encoding="utf-8",
    )
    (parser_dir / "pages.jsonl").write_text(
        json.dumps(
            {
                "evidence_id": f"sha256:{document_hash}:page:1",
                "document_hash": document_hash,
                "pdf_page": 1,
                "text": "",
                "regions": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    pool = evidence_pool_from_publications([tmp_path])
    assert f"sha256:{document_hash}:page:1" in pool
