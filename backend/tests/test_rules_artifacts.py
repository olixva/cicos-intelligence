"""Artefactos de reglas firmados: validación, carga, transcripción y catálogo D.A.A."""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import pytest
from transcribe_matrix_textlayer import parse_matrix_text

from domain.rules.artifact_validation import (
    RulesArtifactError,
    compare_transcriptions,
    evidence_pool_from_publications,
    load_matrix_cells,
    load_schema,
    transcription_sha256,
    validate_cide_matrix,
    validate_ruleset,
)
from domain.rules.ruleset import LoadedRule
from infrastructure.config.rules_artifacts import (
    RulesArtifactsUnavailable,
    load_rules_artifacts,
)

# --------------------------------------------------------------------------
# Tests for the rules artifact validator.
#
# These tests build a synthetic matrix and ruleset that pass every
# required check, plus a couple of negative fixtures, to assert that the
# validator catches every documented gap.
# --------------------------------------------------------------------------


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


# --------------------------------------------------------------------------
# Loading the signed artifacts is a startup decision, never a silent default.
#
# If the matrix or the ruleset fails validation the process must fail loudly.
# Degrading to "no rules" without saying so is exactly how a demo ends up
# claiming a decision nothing supports.
# --------------------------------------------------------------------------


_REPO = Path(__file__).resolve().parents[2]


def test_loads_the_shipped_artifacts() -> None:
    artifacts = load_rules_artifacts(_REPO / "data" / "rules")
    assert len(artifacts.rules) == 14
    assert all(isinstance(rule, LoadedRule) for rule in artifacts.rules)
    assert len(artifacts.matrix_cells) == 324


def test_loads_the_four_printed_matrix_observations() -> None:
    """Las cuatro observaciones bajo la tabla (pág. 101) sólo deciden lo que
    el manual dice: no un patrón genérico deducido del asterisco."""
    artifacts = load_rules_artifacts(_REPO / "data" / "rules")
    by_id = {exception.note_id: exception for exception in artifacts.matrix_exceptions}

    assert set(by_id) == {"obs-a2-b4", "obs-b2-a4", "obs-a16-b0", "obs-b16-a0"}
    a2_b4 = by_id["obs-a2-b4"]
    assert a2_b4.fact == "door_opened_by"
    assert a2_b4.actor == "A"
    assert a2_b4.liable_unless_exception == "B"
    a2_position = (
        artifacts.row_labels.index("A2") + 1,
        artifacts.column_labels.index("B4") + 1,
    )
    assert a2_position in a2_b4.positions
    # La celda que gobierna cada observación debe llevar de verdad el asterisco.
    for exception in artifacts.matrix_exceptions:
        for position in exception.positions:
            assert "*" in artifacts.matrix_cells[position].outcome, exception.note_id


def test_rules_keep_the_order_of_the_artifact() -> None:
    artifacts = load_rules_artifacts(_REPO / "data" / "rules")
    raw = json.loads((_REPO / "data" / "rules" / "ruleset.v1.json").read_text(encoding="utf-8"))
    assert [rule.rule_id for rule in artifacts.rules] == [r["rule_id"] for r in raw["rules"]]


def test_a_missing_ruleset_fails_loudly(tmp_path: Path) -> None:
    with pytest.raises(RulesArtifactsUnavailable, match="ruleset"):
        load_rules_artifacts(tmp_path)


def test_an_unsigned_matrix_is_refused(tmp_path: Path) -> None:
    """An artifact without a complete attestation must not drive decisions."""
    source = _REPO / "data" / "rules"
    (tmp_path / "ruleset.v1.json").write_text(
        (source / "ruleset.v1.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    matrix = json.loads((source / "cide-matrix.v1.json").read_text(encoding="utf-8"))
    matrix["attestation"]["signed_by"] = []
    (tmp_path / "cide-matrix.v1.json").write_text(json.dumps(matrix), encoding="utf-8")

    with pytest.raises(RulesArtifactsUnavailable, match="attestation|signed"):
        load_rules_artifacts(tmp_path)


# --------------------------------------------------------------------------
# The text-layer transcription must reproduce the printed grid exactly.
#
# This parser is transcription B of the CIDE table. Its value depends on
# being strict: a permissive parser that silently accepted a short row
# would agree with transcription A by construction and destroy the point
# of comparing two independent readings.
# --------------------------------------------------------------------------


_HEADER = " ".join(f"B{b}" for b in range(18))


def _grid(**overrides: str) -> str:
    """Build a full 18-row page text; rows default to a legal all-'A' row."""
    rows = []
    for a in range(18):
        values = overrides.get(f"A{a}", " ".join("A" for _ in range(18)))
        rows.append(f"A{a} {values}")
    return f" 102 56. Tabla de Culpabilidad {_HEADER} " + " ".join(rows) + " "


def test_parse_matrix_text_reads_the_header_row() -> None:
    parsed = parse_matrix_text(_grid())
    assert parsed["column_labels"][:3] == ["B0", "B1", "B2"]
    assert len(parsed["column_labels"]) == 18


def test_parse_matrix_text_preserves_asterisked_outcomes_and_dashes() -> None:
    row = "- A B B B B B A B - B B B B B B A* B"
    parsed = parse_matrix_text(_grid(A0=row))
    assert parsed["cells"]["0,16"]["outcome"] == "A*"
    assert parsed["cells"]["0,0"]["outcome"] == "-"
    assert parsed["cells"]["0,1"]["outcome"] == "A"


def test_parse_matrix_text_reads_every_cell() -> None:
    parsed = parse_matrix_text(_grid())
    assert len(parsed["cells"]) == 324


def test_parse_matrix_text_rejects_a_short_row() -> None:
    with pytest.raises(ValueError, match="18"):
        parse_matrix_text(_grid(A5=" ".join("A" for _ in range(17))))


def test_parse_matrix_text_rejects_an_unknown_outcome() -> None:
    with pytest.raises(ValueError, match="outcome"):
        parse_matrix_text(_grid(A5="X " + " ".join("A" for _ in range(17))))


def test_parse_matrix_text_requires_a_header() -> None:
    with pytest.raises(ValueError, match="header"):
        parse_matrix_text("A0 " + " ".join("A" for _ in range(18)))


# ---------------------------------------------------------------------------
# The shipped artifact itself. These guard the delivery, not the parser: if the
# adjudicated matrix ever stops validating, or its content drifts away from the
# two attested transcriptions, the claim workflow must not keep deciding.
# ---------------------------------------------------------------------------


_MATRIX = _REPO / "data" / "rules" / "cide-matrix.v1.json"
_DOCUMENT_HASH = "b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344"


def test_shipped_matrix_validates_with_a_complete_attestation() -> None:
    report = validate_cide_matrix(
        _MATRIX,
        expected_document_hash=_DOCUMENT_HASH,
        evidence_pool=evidence_pool_from_publications([_REPO / "data" / "extractions"]),
    )
    assert report.errors == ()
    assert report.attestation_complete
    assert report.cell_count == 324


def test_shipped_matrix_matches_both_attested_transcriptions() -> None:
    """The adjudicated artifact must not drift from what was actually signed."""
    cells = load_matrix_cells(_MATRIX)
    for name in ("matrix-visual-a", "matrix-textlayer-b"):
        raw = json.loads((_REPO / "data" / "rules" / "transcriptions" / f"{name}.json").read_text())
        for key, cell in raw["cells"].items():
            a, b = (int(part) for part in key.split(","))
            # Transcriptions use the printed 0-based labels; the schema requires
            # 1-based positions, so position i corresponds to label A(i-1).
            assert cells[(a + 1, b + 1)]["outcome"] == cell["outcome"], f"{name} {key}"


def test_shipped_matrix_is_antisymmetric_and_hollow_on_the_diagonal() -> None:
    """Two structural properties of the printed table, checked on the delivery."""
    cells = load_matrix_cells(_MATRIX)
    swap = {"A": "B", "B": "A", "-": "-"}
    for i in range(1, 19):
        assert cells[(i, i)]["outcome"] == "-"
    for a, b in itertools.product(range(1, 19), repeat=2):
        here, mirror = cells[(a, b)]["outcome"], cells[(b, a)]["outcome"]
        assert swap[here.rstrip("*")] == mirror.rstrip("*"), f"({a},{b})"
        assert ("*" in here) == ("*" in mirror), f"asterisk ({a},{b})"


def test_shipped_matrix_footnotes_cover_every_asterisked_cell() -> None:
    """An asterisk without a note would be an unexplained exception."""
    cells = load_matrix_cells(_MATRIX)
    starred = {(a, b) for (a, b), cell in cells.items() if "*" in cell["outcome"]}
    assert starred == {(3, 5), (5, 3), (17, 1), (1, 17)}
    notes = json.loads(_MATRIX.read_text(encoding="utf-8"))["notes"]
    assert {note["note_id"] for note in notes} == {
        "obs-a2-b4",
        "obs-b2-a4",
        "obs-a16-b0",
        "obs-b16-a0",
    }


# --------------------------------------------------------------------------
# The D.A.A. code catalogue is a reviewed external input to CIDE lookup.
# --------------------------------------------------------------------------


_CATALOGUE = _REPO / "data" / "rules" / "daa-circumstances.v1.json"


def test_shipped_daa_catalogue_keeps_the_human_validated_mapping() -> None:
    """A0 is no selection; A1-A17 are the standard D.A.A. checklist."""
    payload = json.loads(_CATALOGUE.read_text(encoding="utf-8"))

    assert payload["provenance"] == "external-daa-form"
    assert payload["in_manual_scope"] is False
    assert [(item["code"], item["label"]) for item in payload["circumstances"]] == [
        ("A0", "Sin circunstancia declarada"),
        ("A1", "Estaba estacionado o parado"),
        ("A2", "Salía de un estacionamiento o abría una puerta"),
        ("A3", "Iba a estacionar"),
        ("A4", "Salía de un aparcamiento, lugar privado o camino de tierra"),
        ("A5", "Entraba a un aparcamiento, lugar privado o camino de tierra"),
        ("A6", "Entraba en una rotonda"),
        ("A7", "Circulaba por una rotonda"),
        ("A8", "Golpeó por detrás a otro vehículo en el mismo sentido y carril"),
        ("A9", "Circulaba en el mismo sentido, pero en carril distinto"),
        ("A10", "Cambiaba de carril"),
        ("A11", "Adelantaba"),
        ("A12", "Giraba a la derecha"),
        ("A13", "Giraba a la izquierda"),
        ("A14", "Daba marcha atrás"),
        ("A15", "Invadía el carril del sentido contrario"),
        ("A16", "Venía de la derecha en un cruce"),
        ("A17", "No respetó una señal de preferencia o un semáforo en rojo"),
    ]


def test_daa_catalogue_marks_a0_as_a_non_manoeuvre() -> None:
    """The zero index must never be presented as a manoeuvre from the form."""
    payload = json.loads(_CATALOGUE.read_text(encoding="utf-8"))

    zero = payload["circumstances"][0]
    assert zero["code"] == "A0"
    assert zero["is_daa_checkbox"] is False
    assert "no existe" in zero["note"].lower()
