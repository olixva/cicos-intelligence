from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest
from pypdf import PdfWriter


def test_rejects_an_unexpected_document(tmp_path: Path) -> None:
    """Changing the expected digest must prevent a manifest from being returned."""
    from bootstrap import build_inspect_manual
    from domain.models.document import SourceIntegrityError

    source = tmp_path / "manual.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(str(source))

    with pytest.raises(SourceIntegrityError):
        build_inspect_manual().execute(source, expected_sha256="0" * 64)


def test_returns_manifest_with_hash_filename_and_page_count(tmp_path: Path) -> None:
    """Changing any input byte or page must change the exposed manifest facts."""
    from bootstrap import build_inspect_manual

    source = tmp_path / "manual.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_blank_page(width=300, height=300)
    writer.write(str(source))
    expected_hash = sha256(source.read_bytes()).hexdigest()

    manifest = build_inspect_manual().execute(source, expected_sha256=expected_hash)

    assert manifest.document_id == f"sha256:{expected_hash}"
    assert manifest.sha256 == expected_hash
    assert manifest.filename == "manual.pdf"
    assert manifest.page_count == 2


def test_rejects_non_pdf_bytes(tmp_path: Path) -> None:
    """Replacing a PDF with arbitrary bytes must reject the source as unreadable."""
    from bootstrap import build_inspect_manual
    from domain.models.document import SourceInspectionError

    source = tmp_path / "not-a-pdf.pdf"
    source.write_bytes(b"not a PDF")

    with pytest.raises(SourceInspectionError, match="readable PDF"):
        build_inspect_manual().execute(source)


def test_rejects_a_missing_source(tmp_path: Path) -> None:
    """Removing the source file must produce a readable input error."""
    from bootstrap import build_inspect_manual
    from domain.models.document import SourceInspectionError

    with pytest.raises(SourceInspectionError, match="Unable to read source"):
        build_inspect_manual().execute(tmp_path / "missing.pdf")


def test_rejects_an_encrypted_pdf(tmp_path: Path) -> None:
    """Encrypting an otherwise valid PDF must prevent inspection."""
    from bootstrap import build_inspect_manual
    from domain.models.document import SourceInspectionError

    source = tmp_path / "encrypted.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.encrypt("secret")
    writer.write(str(source))

    with pytest.raises(SourceInspectionError, match="Encrypted PDF"):
        build_inspect_manual().execute(source)


def test_rejects_a_pdf_without_pages(tmp_path: Path) -> None:
    """Removing all pages from a structurally valid PDF must reject the source."""
    from bootstrap import build_inspect_manual
    from domain.models.document import SourceInspectionError

    source = tmp_path / "empty.pdf"
    PdfWriter().write(str(source))

    with pytest.raises(SourceInspectionError, match="at least one page"):
        build_inspect_manual().execute(source)
