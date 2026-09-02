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
