"""Transcription B of the CIDE table, read from the pypdf text layer.

Independent from the visual reading of the rendered page: the two share
no extraction path, so agreement between them is evidence rather than
tautology. The parser is deliberately strict — it refuses a row that
does not carry exactly 18 recognised outcomes rather than padding it.
"""

import argparse
import json
import re
from pathlib import Path

DOCUMENT_HASH = "b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344"
MATRIX_PDF_PAGE = 101
_SIZE = 18
_OUTCOMES = frozenset({"A", "B", "-", "A*", "B*"})
_HEADER = re.compile(r"\bB0\b\s+B1\b(?:\s+B\d+\b){16}")


def parse_matrix_text(text: str) -> dict[str, object]:
    """Parse the printed 18x18 grid out of the page's text layer."""
    header = _HEADER.search(text)
    if header is None:
        raise ValueError("matrix header row B0..B17 not found in the page text")
    column_labels = header.group(0).split()
    body = text[header.end() :]
    cells: dict[str, dict[str, object]] = {}
    row_labels: list[str] = []
    for a in range(_SIZE):
        label = f"A{a}"
        # Anchor on this row's label and stop at the next one, so a row that
        # lost a value cannot silently borrow from its neighbour.
        start = re.search(rf"\b{label}\b", body)
        if start is None:
            raise ValueError(f"row {label} not found in the page text")
        following = re.search(rf"\bA{a + 1}\b", body) if a + 1 < _SIZE else None
        chunk = body[start.end() : following.start() if following else None]
        values = chunk.split()
        if a + 1 == _SIZE:
            values = values[:_SIZE]
        if len(values) != _SIZE:
            raise ValueError(f"row {label} carries {len(values)} values, expected {_SIZE}")
        for b, outcome in enumerate(values):
            if outcome not in _OUTCOMES:
                raise ValueError(f"row {label} column B{b} has unknown outcome {outcome!r}")
            cells[f"{a},{b}"] = {"a": a, "b": b, "outcome": outcome}
        row_labels.append(label)
        body = body[start.end() :]
    return {"row_labels": row_labels, "column_labels": column_labels, "cells": cells}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pages", type=Path, required=True, help="pages.jsonl of a publication")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    page_text: str | None = None
    for raw in args.pages.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        record = json.loads(raw)
        if record.get("pdf_page") == MATRIX_PDF_PAGE:
            page_text = record.get("text") or ""
            break
    if page_text is None:
        raise SystemExit(f"page {MATRIX_PDF_PAGE} not found in {args.pages}")

    parsed = parse_matrix_text(page_text)
    document = {
        "transcription_id": "matrix-textlayer-b",
        "method": "pypdf-text-layer",
        "reviewer_id": "claude-textlayer-b",
        "pdf_page": MATRIX_PDF_PAGE,
        "document_hash": DOCUMENT_HASH,
        **parsed,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"{args.output} ({len(parsed['cells'])} cells)")  # pyright: ignore[reportArgumentType]


if __name__ == "__main__":
    main()
