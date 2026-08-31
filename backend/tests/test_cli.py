from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.base_models import ConversionStatus, InputFormat
from docling.datamodel.document import ConversionResult, InputDocument
from docling.document_converter import DocumentConverter
from docling_core.types.doc.base import Size
from docling_core.types.doc.document import DoclingDocument
from pypdf import PdfWriter
from pytest import CaptureFixture


def test_inspect_manual_prints_a_json_manifest(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    """A valid source must return its manifest as JSON on standard output."""
    from infrastructure.adapters.inbound.cli.main import main

    source = tmp_path / "manual.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(str(source))
    expected_hash = sha256(source.read_bytes()).hexdigest()

    result = main(["inspect-manual", str(source), "--expected-sha256", expected_hash])

    captured = capsys.readouterr()
    assert result == 0
    assert json.loads(captured.out) == {
        "document_id": f"sha256:{expected_hash}",
        "filename": "manual.pdf",
        "page_count": 1,
        "sha256": expected_hash,
    }
    assert captured.err == ""


def test_inspect_manual_reports_input_errors_without_a_traceback(
    capsys: CaptureFixture[str], tmp_path: Path
) -> None:
    """An unreadable input must be a concise CLI error with status 2."""
    from infrastructure.adapters.inbound.cli.main import main

    result = main(["inspect-manual", str(tmp_path / "missing.pdf")])

    captured = capsys.readouterr()
    assert result == 2
    assert captured.out == ""
    assert "Unable to read source" in captured.err
    assert "Traceback" not in captured.err


def test_ingest_docling_prints_metadata_without_binary_assets(
    capsys: CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Serializing a structured extraction must never send original or PNG bytes to stdout."""
    from io import BytesIO

    from infrastructure.adapters.inbound.cli.main import main

    source = tmp_path / "manual.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=100)
    writer.write(source)
    original = source.read_bytes()
    document = DoclingDocument(name="manual")
    document.add_page(1, Size(width=200, height=100))
    converted = ConversionResult(
        input=InputDocument(
            path_or_stream=BytesIO(original),
            format=InputFormat.PDF,
            backend=PyPdfiumDocumentBackend,
            filename=source.name,
        ),
        document=document,
        status=ConversionStatus.SUCCESS,
    )

    def convert(*args: Any, **kwargs: Any) -> ConversionResult:
        return converted

    monkeypatch.setattr(DocumentConverter, "convert", convert)

    result = main(
        [
            "ingest",
            str(source),
            "--parser",
            "docling",
            "--output",
            str(tmp_path / "evidence"),
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert result == 0
    assert captured.err == ""
    assert payload["document_id"] == f"sha256:{sha256(original).hexdigest()}"
    assert payload["page_count"] == 1
    assert payload["parser"].startswith("docling-2.124.0-pdfium-5.13.0-")
    assert {asset["path"] for asset in payload["assets"]} >= {
        "original.pdf",
        "pages/1.png",
        "document.json",
        "document.md",
        "diagnostics.json",
    }
    assert original.hex() not in captured.out


def test_ingest_reports_source_errors_without_a_traceback(
    capsys: CaptureFixture[str], tmp_path: Path
) -> None:
    """A missing ingestion source must return status 2 without partial JSON output."""
    from infrastructure.adapters.inbound.cli.main import main

    result = main(
        [
            "ingest",
            str(tmp_path / "missing.pdf"),
            "--parser",
            "pypdf",
            "--output",
            str(tmp_path / "evidence"),
        ]
    )

    captured = capsys.readouterr()
    assert result == 2
    assert captured.out == ""
    assert "Unable to read source" in captured.err
    assert "Traceback" not in captured.err
