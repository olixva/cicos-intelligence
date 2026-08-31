from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from _pytest.capture import CaptureFixture
from pypdf import PdfWriter


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
