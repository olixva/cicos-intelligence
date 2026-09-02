"""The text-layer transcription must reproduce the printed grid exactly.

This parser is transcription B of the CIDE table. Its value depends on
being strict: a permissive parser that silently accepted a short row
would agree with transcription A by construction and destroy the point
of comparing two independent readings.
"""

import sys
from pathlib import Path

import pytest

# Same convention as test_ingestion_publication_contract.py: backend/scripts
# holds standalone tools that are not part of the installed package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from transcribe_matrix_textlayer import parse_matrix_text  # noqa: E402

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

import itertools  # noqa: E402
import json  # noqa: E402

from domain.rules.artifact_validation import (  # noqa: E402
    evidence_pool_from_publications,
    load_matrix_cells,
    validate_cide_matrix,
)

_REPO = Path(__file__).resolve().parents[2]
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
