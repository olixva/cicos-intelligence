from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from pypdf import PdfWriter


def _blank_pdf(path: Path, pages: int = 2) -> None:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    writer.write(str(path))


def test_keeps_empty_pages(tmp_path: Path) -> None:
    """Dropping a physical blank page would lose evidence from the manual."""
    from infrastructure.adapters.outbound.document_parser.pypdf_parser import PypdfDocumentParser

    source = tmp_path / "blank.pdf"
    _blank_pdf(source)

    extraction = PypdfDocumentParser().parse(source)

    assert [page.pdf_page for page in extraction.pages] == [1, 2]
    assert [page.text for page in extraction.pages] == ["", ""]
    assert extraction.warnings == (
        "Page 1 did not yield extractable text",
        "Page 2 did not yield extractable text",
    )


def test_publishes_complete_page_evidence_under_its_parser_version(tmp_path: Path) -> None:
    """Changing a page or parser must not overwrite the recorded page evidence."""
    from infrastructure.adapters.outbound.document_parser.pypdf_parser import PypdfDocumentParser
    from infrastructure.adapters.outbound.evidence_repository.filesystem_repository import (
        EvidencePublicationError,
        FilesystemEvidenceRepository,
    )

    source = tmp_path / "blank.pdf"
    _blank_pdf(source)
    extraction = PypdfDocumentParser().parse(source)
    repository = FilesystemEvidenceRepository(tmp_path / "extractions", extraction.parser)

    published = repository.publish(extraction)

    assert published == tmp_path / "extractions" / extraction.manifest.sha256 / extraction.parser
    assert json.loads((published / "manifest.json").read_text()) == {
        "document_id": extraction.manifest.document_id,
        "filename": "blank.pdf",
        "page_count": 2,
        "sha256": extraction.manifest.sha256,
    }
    page_lines = (published / "pages.jsonl").read_text().splitlines()
    assert [json.loads(line)["pdf_page"] for line in page_lines] == [1, 2]
    assert repository.get(extraction.pages[1].evidence_id) == extraction.pages[1]

    altered_page = replace(extraction.pages[0], text="changed evidence")
    altered = replace(extraction, pages=(altered_page, extraction.pages[1]))
    with pytest.raises(EvidencePublicationError, match="different content"):
        repository.publish(altered)
    assert repository.get(extraction.pages[0].evidence_id).text == ""


def test_aborted_publication_leaves_no_final_evidence_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A write error must not expose a partially-written evidence version."""
    from infrastructure.adapters.outbound.document_parser.pypdf_parser import PypdfDocumentParser
    from infrastructure.adapters.outbound.evidence_repository import filesystem_repository
    from infrastructure.adapters.outbound.evidence_repository.filesystem_repository import (
        FilesystemEvidenceRepository,
    )

    source = tmp_path / "blank.pdf"
    _blank_pdf(source)
    extraction = PypdfDocumentParser().parse(source)
    repository = FilesystemEvidenceRepository(tmp_path / "extractions", extraction.parser)
    original_dump = filesystem_repository.json.dump
    calls = 0

    def fail_during_second_page(obj: object, file: Any, **kwargs: Any) -> None:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise OSError("disk full")
        original_dump(obj, file, **kwargs)

    monkeypatch.setattr(filesystem_repository.json, "dump", fail_during_second_page)

    with pytest.raises(OSError, match="disk full"):
        repository.publish(extraction)

    assert not (tmp_path / "extractions" / extraction.manifest.sha256 / extraction.parser).exists()


def test_get_rejects_identifier_that_cannot_name_a_page(tmp_path: Path) -> None:
    """A supplied identifier must never be usable as a filesystem path."""
    from infrastructure.adapters.outbound.evidence_repository.filesystem_repository import (
        EvidenceNotFoundError,
        FilesystemEvidenceRepository,
    )

    repository = FilesystemEvidenceRepository(tmp_path / "extractions", "pypdf-6.16.2")

    with pytest.raises(EvidenceNotFoundError, match="Invalid evidence identifier"):
        repository.get("sha256:../../outside:page:1")


def test_get_rejects_a_malformed_stored_page_record(tmp_path: Path) -> None:
    """Corrupt JSON must remain a repository error rather than leak an implementation error."""
    from infrastructure.adapters.outbound.document_parser.pypdf_parser import PypdfDocumentParser
    from infrastructure.adapters.outbound.evidence_repository.filesystem_repository import (
        EvidenceNotFoundError,
        FilesystemEvidenceRepository,
    )

    source = tmp_path / "blank.pdf"
    _blank_pdf(source)
    extraction = PypdfDocumentParser().parse(source)
    repository = FilesystemEvidenceRepository(tmp_path / "extractions", extraction.parser)
    published = repository.publish(extraction)
    (published / "pages.jsonl").write_text("[]\n", encoding="utf-8")

    with pytest.raises(EvidenceNotFoundError, match="Stored evidence is unreadable"):
        repository.get(extraction.pages[0].evidence_id)


def test_get_rejects_a_corrupt_stored_manifest(tmp_path: Path) -> None:
    """A page cannot be trusted when its persisted manifest is malformed."""
    from infrastructure.adapters.outbound.document_parser.pypdf_parser import PypdfDocumentParser
    from infrastructure.adapters.outbound.evidence_repository.filesystem_repository import (
        EvidenceNotFoundError,
        FilesystemEvidenceRepository,
    )

    source = tmp_path / "blank.pdf"
    _blank_pdf(source)
    extraction = PypdfDocumentParser().parse(source)
    repository = FilesystemEvidenceRepository(tmp_path / "extractions", extraction.parser)
    published = repository.publish(extraction)
    (published / "manifest.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(EvidenceNotFoundError, match="Stored evidence is unreadable"):
        repository.get(extraction.pages[0].evidence_id)


def test_get_rejects_page_with_a_mismatched_document_hash(tmp_path: Path) -> None:
    """A returned page must be tied to the hash encoded in its evidence identifier."""
    from infrastructure.adapters.outbound.document_parser.pypdf_parser import PypdfDocumentParser
    from infrastructure.adapters.outbound.evidence_repository.filesystem_repository import (
        EvidenceNotFoundError,
        FilesystemEvidenceRepository,
    )

    source = tmp_path / "blank.pdf"
    _blank_pdf(source)
    extraction = PypdfDocumentParser().parse(source)
    repository = FilesystemEvidenceRepository(tmp_path / "extractions", extraction.parser)
    published = repository.publish(extraction)
    records = [json.loads(line) for line in (published / "pages.jsonl").read_text().splitlines()]
    records[0]["document_hash"] = "0" * 64
    (published / "pages.jsonl").write_text(
        "".join(f"{json.dumps(record, sort_keys=True)}\n" for record in records), encoding="utf-8"
    )

    with pytest.raises(EvidenceNotFoundError, match="Stored evidence is inconsistent"):
        repository.get(extraction.pages[0].evidence_id)


def test_get_rejects_page_with_non_string_text(tmp_path: Path) -> None:
    """Text evidence must retain its stored type instead of coercing corruption to text."""
    from infrastructure.adapters.outbound.document_parser.pypdf_parser import PypdfDocumentParser
    from infrastructure.adapters.outbound.evidence_repository.filesystem_repository import (
        EvidenceNotFoundError,
        FilesystemEvidenceRepository,
    )

    source = tmp_path / "blank.pdf"
    _blank_pdf(source)
    extraction = PypdfDocumentParser().parse(source)
    repository = FilesystemEvidenceRepository(tmp_path / "extractions", extraction.parser)
    published = repository.publish(extraction)
    records = [json.loads(line) for line in (published / "pages.jsonl").read_text().splitlines()]
    records[0]["text"] = 42
    (published / "pages.jsonl").write_text(
        "".join(f"{json.dumps(record, sort_keys=True)}\n" for record in records), encoding="utf-8"
    )

    with pytest.raises(EvidenceNotFoundError, match="Stored evidence is unreadable"):
        repository.get(extraction.pages[0].evidence_id)
