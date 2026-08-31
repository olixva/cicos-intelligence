"""Filesystem publication of immutable, parser-versioned page evidence."""

import json
import re
import shutil
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import cast

from domain.models.evidence import Extraction, PageEvidence

_PARSER_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_EVIDENCE_ID_PATTERN = re.compile(r"sha256:([0-9a-f]{64}):page:([1-9][0-9]*)")


class EvidencePublicationError(Exception):
    """Raised when an extraction cannot be published immutably."""


class EvidenceNotFoundError(Exception):
    """Raised when a valid page identifier cannot be retrieved."""


class FilesystemEvidenceRepository:
    """Store evidence under an explicit parser version, never a guessed one."""

    def __init__(self, root: Path, parser: str) -> None:
        if not _PARSER_PATTERN.fullmatch(parser):
            raise ValueError("Parser version must be a safe path component")
        self._root = root
        self._parser = parser

    def publish(self, extraction: Extraction) -> Path:
        """Write and validate a complete extraction before atomically publishing it."""
        self._validate_extraction(extraction)
        destination = self._root / extraction.manifest.sha256 / self._parser
        if destination.exists():
            if self._matches(extraction, destination):
                return destination
            raise EvidencePublicationError("Evidence version already exists with different content")

        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=f".{self._parser}.", dir=destination.parent))
        try:
            self._write_extraction(extraction, temporary)
            self._validate_published(extraction, temporary)
            try:
                temporary.rename(destination)
            except OSError as error:
                if destination.exists() and self._matches(extraction, destination):
                    return destination
                raise EvidencePublicationError(
                    "Evidence version already exists with different content"
                ) from error
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
        return destination

    def get(self, evidence_id: str) -> PageEvidence:
        """Read one evidence record through an identifier validated before path use."""
        match = _EVIDENCE_ID_PATTERN.fullmatch(evidence_id)
        if match is None:
            raise EvidenceNotFoundError("Invalid evidence identifier")
        document_hash, requested_page = match.groups()
        pages_file = self._root / document_hash / self._parser / "pages.jsonl"
        try:
            lines = pages_file.read_text(encoding="utf-8").splitlines()
        except OSError as error:
            raise EvidenceNotFoundError("Evidence version was not found") from error
        for line in lines:
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise EvidenceNotFoundError("Stored evidence is unreadable") from error
            evidence = _page_evidence(record)
            if evidence.evidence_id != evidence_id:
                continue
            if evidence.pdf_page != int(requested_page):
                raise EvidenceNotFoundError("Stored evidence is inconsistent")
            return evidence
        raise EvidenceNotFoundError("Evidence page was not found")

    def _validate_extraction(self, extraction: Extraction) -> None:
        if extraction.parser != self._parser:
            raise EvidencePublicationError("Extraction parser does not match repository parser")
        manifest = extraction.manifest
        if not re.fullmatch(r"[0-9a-f]{64}", manifest.sha256):
            raise EvidencePublicationError("Manifest SHA-256 is invalid")
        if manifest.document_id != f"sha256:{manifest.sha256}":
            raise EvidencePublicationError("Manifest document identifier is invalid")
        if len(extraction.pages) != manifest.page_count:
            raise EvidencePublicationError("Extraction page count does not match manifest")
        for expected_number, page in enumerate(extraction.pages, start=1):
            if (
                page.document_hash != manifest.sha256
                or page.pdf_page != expected_number
                or page.evidence_id != f"{manifest.document_id}:page:{expected_number}"
            ):
                raise EvidencePublicationError("Extraction page identity is invalid")

    def _write_extraction(self, extraction: Extraction, directory: Path) -> None:
        with (directory / "manifest.json").open("w", encoding="utf-8") as manifest_file:
            json.dump(asdict(extraction.manifest), manifest_file, sort_keys=True)
            manifest_file.write("\n")
        with (directory / "pages.jsonl").open("w", encoding="utf-8") as pages_file:
            for page in extraction.pages:
                json.dump(_page_record(page), pages_file, sort_keys=True)
                pages_file.write("\n")

    def _validate_published(self, extraction: Extraction, directory: Path) -> None:
        stored_manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        stored_pages = [
            json.loads(line)
            for line in (directory / "pages.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        if (
            stored_manifest != asdict(extraction.manifest)
            or len(stored_pages) != extraction.manifest.page_count
        ):
            raise EvidencePublicationError("Written evidence does not match the extraction")
        if stored_pages != [_page_record(page) for page in extraction.pages]:
            raise EvidencePublicationError("Written page evidence does not match the extraction")

    def _matches(self, extraction: Extraction, directory: Path) -> bool:
        try:
            self._validate_published(extraction, directory)
        except EvidencePublicationError, OSError, json.JSONDecodeError:
            return False
        return True


def _page_evidence(record: object) -> PageEvidence:
    """Decode one JSON evidence record into its immutable domain representation."""
    if not isinstance(record, dict):
        raise EvidenceNotFoundError("Stored evidence is unreadable")
    record = cast(dict[str, object], record)
    try:
        raw_regions = record["regions"]
        if not isinstance(raw_regions, list):
            raise ValueError("Invalid regions")
        raw_regions = cast(list[object], raw_regions)
        regions = tuple(_region(region) for region in raw_regions)
        return PageEvidence(
            evidence_id=str(record["evidence_id"]),
            document_hash=str(record["document_hash"]),
            pdf_page=_page_number(record["pdf_page"]),
            text=str(record["text"]),
            printed_label=_optional_string(record["printed_label"]),
            image_path=_optional_string(record["image_path"]),
            regions=regions,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise EvidenceNotFoundError("Stored evidence is unreadable") from error


def _page_record(page: PageEvidence) -> dict[str, object]:
    """Produce the JSON-compatible representation used for one page record."""
    record = asdict(page)
    record["regions"] = [list(region) for region in page.regions]
    return record


def _optional_string(value: object) -> str | None:
    if value is None or isinstance(value, str):
        return value
    raise ValueError("Expected a string or null")


def _region(value: object) -> tuple[float, float, float, float]:
    if not isinstance(value, list):
        raise ValueError("Invalid region")
    value = cast(list[object], value)
    if len(value) != 4:
        raise ValueError("Invalid region")
    first, second, third, fourth = value
    return (
        _number(first),
        _number(second),
        _number(third),
        _number(fourth),
    )


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("Expected a number")
    return float(value)


def _page_number(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("Expected a positive page number")
    return value
