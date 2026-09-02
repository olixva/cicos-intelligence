"""Filesystem publication of immutable, parser-versioned page evidence."""

import json
import re
import shutil
import tempfile
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import cast

from domain.models.document import DocumentManifest
from domain.models.evidence import ElementEvidence, Extraction, PageEvidence

_PARSER_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_EVIDENCE_ID_PATTERN = re.compile(r"sha256:([0-9a-f]{64}):page:([1-9][0-9]*)")
_PUBLICATION_NAME = "publication.json"
_RESERVED_PATHS = {"manifest.json", "pages.jsonl", "extraction.json", _PUBLICATION_NAME}


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
        pages = self.get_document_pages(document_hash)
        page_index = int(requested_page) - 1
        if page_index >= len(pages):
            raise EvidenceNotFoundError("Evidence page was not found")
        return pages[page_index]

    def get_document_pages(self, document_hash: str) -> tuple[PageEvidence, ...]:
        """Read every page from one fully verified, parser-versioned publication."""
        if re.fullmatch(r"[0-9a-f]{64}", document_hash) is None:
            raise EvidenceNotFoundError("Invalid document hash")
        directory = self._root / document_hash / self._parser
        publication_files = _validate_publication_root(directory)
        try:
            manifest_record = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            page_records = [
                json.loads(line)
                for line in (directory / "pages.jsonl").read_text(encoding="utf-8").splitlines()
            ]
        except (OSError, json.JSONDecodeError) as error:
            raise EvidenceNotFoundError("Evidence version was not found") from error
        manifest = _document_manifest(manifest_record)
        if manifest.sha256 != document_hash:
            raise EvidenceNotFoundError("Stored evidence is inconsistent")
        pages = tuple(_page_evidence(record) for record in page_records)
        _validate_stored_pages(manifest, pages)
        _validate_stored_assets(directory, manifest, pages, self._parser, publication_files)
        return pages

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

        asset_paths: set[str] = set()
        for asset in extraction.assets:
            if not _is_safe_asset_path(asset.path) or asset.path in asset_paths:
                raise EvidencePublicationError("Invalid or duplicate asset path")
            asset_paths.add(asset.path)
            if asset.path == "original.pdf" and sha256(asset.data).hexdigest() != manifest.sha256:
                raise EvidencePublicationError("The original asset does not match the source hash")
        for path in asset_paths:
            if any(str(parent) in asset_paths for parent in PurePosixPath(path).parents):
                raise EvidencePublicationError("Asset paths overlap")
        for page in extraction.pages:
            if page.image_path is not None and page.image_path not in asset_paths:
                raise EvidencePublicationError("Page image is missing its asset")
            for element in page.elements:
                if not element.element_id.startswith(f"{manifest.document_id}:element:"):
                    raise EvidencePublicationError("Element identity is not source-based")

    def _write_extraction(self, extraction: Extraction, directory: Path) -> None:
        with (directory / "manifest.json").open("w", encoding="utf-8") as manifest_file:
            json.dump(
                _canonical_manifest_record(extraction.manifest), manifest_file, sort_keys=True
            )
            manifest_file.write("\n")
        with (directory / "pages.jsonl").open("w", encoding="utf-8") as pages_file:
            for page in extraction.pages:
                json.dump(_page_record(page), pages_file, sort_keys=True)
                pages_file.write("\n")

        if extraction.assets or any(page.elements for page in extraction.pages):
            (directory / "extraction.json").write_text(
                json.dumps(_extraction_record(extraction), sort_keys=True) + "\n", encoding="utf-8"
            )
        for asset in extraction.assets:
            target = directory / asset.path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(asset.data)
        _write_publication_root(directory)

    def _validate_published(self, extraction: Extraction, directory: Path) -> None:
        try:
            publication_files = _validate_publication_root(directory)
        except EvidenceNotFoundError as error:
            raise EvidencePublicationError("Written publication is inconsistent") from error
        stored_manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        stored_pages = [
            json.loads(line)
            for line in (directory / "pages.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        if (
            stored_manifest != _canonical_manifest_record(extraction.manifest)
            or len(stored_pages) != extraction.manifest.page_count
        ):
            raise EvidencePublicationError("Written evidence does not match the extraction")
        # T2 records omitted optional layout fields; retain compatibility on repeat ingestion.
        expected_pages = [_page_record(page) for page in extraction.pages]
        for record in stored_pages:
            for key in ("elements", "width", "height"):
                if key in record and record[key] in (None, []):
                    del record[key]
        if stored_pages != expected_pages:
            raise EvidencePublicationError("Written page evidence does not match the extraction")

        if extraction.assets or any(page.elements for page in extraction.pages):
            metadata = json.loads((directory / "extraction.json").read_text(encoding="utf-8"))
            if metadata != _extraction_record(extraction):
                raise EvidencePublicationError("Written extraction metadata does not match")
        for asset in extraction.assets:
            target = directory / asset.path
            if target.is_symlink() or target.read_bytes() != asset.data:
                raise EvidencePublicationError("Written asset does not match the extraction")
        try:
            _validate_stored_assets(
                directory,
                extraction.manifest,
                extraction.pages,
                extraction.parser,
                publication_files,
            )
        except EvidenceNotFoundError as error:
            raise EvidencePublicationError("Written assets are inconsistent") from error

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
            evidence_id=_required_string(record["evidence_id"]),
            document_hash=_required_string(record["document_hash"]),
            pdf_page=_page_number(record["pdf_page"]),
            text=_required_string(record["text"]),
            printed_label=_optional_string(record["printed_label"]),
            image_path=_optional_string(record["image_path"]),
            regions=regions,
            elements=_elements(record.get("elements", [])),
            width=_optional_number(record.get("width")),
            height=_optional_number(record.get("height")),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise EvidenceNotFoundError("Stored evidence is unreadable") from error


def _document_manifest(record: object) -> DocumentManifest:
    """Decode and validate the identity of a persisted extraction manifest."""
    if not isinstance(record, dict):
        raise EvidenceNotFoundError("Stored evidence is unreadable")
    record = cast(dict[str, object], record)
    try:
        manifest = DocumentManifest(
            document_id=_required_string(record["document_id"]),
            sha256=_required_string(record["sha256"]),
            filename=_required_string(record["filename"]),
            page_count=_page_number(record["page_count"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise EvidenceNotFoundError("Stored evidence is unreadable") from error
    if (
        re.fullmatch(r"[0-9a-f]{64}", manifest.sha256) is None
        or manifest.document_id != f"sha256:{manifest.sha256}"
    ):
        raise EvidenceNotFoundError("Stored evidence is unreadable")
    return manifest


def _validate_stored_pages(manifest: DocumentManifest, pages: tuple[PageEvidence, ...]) -> None:
    """Require every persisted physical page to match the persisted manifest identity."""
    if len(pages) != manifest.page_count:
        raise EvidenceNotFoundError("Stored evidence is inconsistent")
    for expected_page, page in enumerate(pages, start=1):
        if (
            page.document_hash != manifest.sha256
            or page.pdf_page != expected_page
            or page.evidence_id != f"{manifest.document_id}:page:{expected_page}"
        ):
            raise EvidenceNotFoundError("Stored evidence is inconsistent")
        if any(
            not element.element_id.startswith(f"{manifest.document_id}:element:")
            for element in page.elements
        ):
            raise EvidenceNotFoundError("Stored evidence is inconsistent")


def _validate_stored_assets(
    directory: Path,
    manifest: DocumentManifest,
    pages: tuple[PageEvidence, ...],
    parser: str,
    publication_files: dict[str, tuple[str, int]],
) -> None:
    """Bind every listed byte asset and page reference to its persisted hash metadata."""
    metadata_path = directory / "extraction.json"
    if not metadata_path.exists():
        if any(page.image_path is not None or page.elements for page in pages) or not (
            set(publication_files) <= {"manifest.json", "pages.jsonl", "original.pdf"}
            and {"manifest.json", "pages.jsonl"} <= set(publication_files)
        ):
            raise EvidenceNotFoundError("Stored evidence is inconsistent")
        return
    try:
        metadata_value: object = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EvidenceNotFoundError("Stored evidence is inconsistent") from error
    if not isinstance(metadata_value, dict):
        raise EvidenceNotFoundError("Stored evidence is inconsistent")
    metadata = cast(dict[str, object], metadata_value)
    if set(metadata) != {"parser", "warnings", "assets"}:
        raise EvidenceNotFoundError("Stored evidence is inconsistent")
    if metadata["parser"] != parser:
        raise EvidenceNotFoundError("Stored evidence is inconsistent")
    warnings_value = metadata["warnings"]
    assets_value = metadata["assets"]
    if (
        not isinstance(warnings_value, list)
        or not all(isinstance(warning, str) for warning in cast(list[object], warnings_value))
        or not isinstance(assets_value, list)
    ):
        raise EvidenceNotFoundError("Stored evidence is inconsistent")
    assets = cast(list[object], assets_value)

    paths: set[str] = set()
    original_digest: str | None = None
    for value in assets:
        if not isinstance(value, dict):
            raise EvidenceNotFoundError("Stored evidence is inconsistent")
        record = cast(dict[str, object], value)
        if set(record) != {"path", "sha256", "size"}:
            raise EvidenceNotFoundError("Stored evidence is inconsistent")
        path = record["path"]
        digest = record["sha256"]
        size = record["size"]
        if (
            not isinstance(path, str)
            or not _is_safe_asset_path(path)
            or path in paths
            or not isinstance(digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            or isinstance(size, bool)
            or not isinstance(size, int)
            or size < 0
        ):
            raise EvidenceNotFoundError("Stored evidence is inconsistent")
        paths.add(path)
        if path == "original.pdf":
            original_digest = digest
        if publication_files.get(path) != (digest, size):
            raise EvidenceNotFoundError("Stored evidence is inconsistent")

    if paths and "original.pdf" not in paths:
        raise EvidenceNotFoundError("Stored evidence is inconsistent")
    if original_digest is not None and original_digest != manifest.sha256:
        raise EvidenceNotFoundError("Stored evidence is inconsistent")
    if any(page.image_path is not None and page.image_path not in paths for page in pages):
        raise EvidenceNotFoundError("Stored evidence is inconsistent")

    expected_files = {"manifest.json", "pages.jsonl", "extraction.json", *paths}
    if set(publication_files) != expected_files:
        raise EvidenceNotFoundError("Stored evidence is inconsistent")


def _is_safe_asset_path(value: str) -> bool:
    path = PurePosixPath(value)
    return not (
        path.is_absolute()
        or ".." in path.parts
        or "\\" in value
        or not path.parts
        or str(path) != value
        or path.parts[0] in _RESERVED_PATHS
    )


def _is_safe_publication_path(value: str) -> bool:
    path = PurePosixPath(value)
    return not (
        path.is_absolute()
        or ".." in path.parts
        or "\\" in value
        or not path.parts
        or str(path) != value
        or path.parts[0] == _PUBLICATION_NAME
    )


def _contains_symlink(path: Path, root: Path) -> bool:
    """Check every publication-relative component before crossing it to read bytes."""
    try:
        relative = path.relative_to(root)
    except ValueError:
        return True
    current = root
    if current.is_symlink():
        return True
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            return True
    return False


def _canonical_manifest_record(manifest: DocumentManifest) -> dict[str, object]:
    """Persist source identity independently from the caller's informational filename alias."""
    return {
        "document_id": manifest.document_id,
        "sha256": manifest.sha256,
        "filename": f"{manifest.sha256}.pdf",
        "page_count": manifest.page_count,
    }


def _canonical_json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _write_publication_root(directory: Path) -> None:
    files: list[dict[str, object]] = []
    for entry in directory.rglob("*"):
        if entry.is_symlink():
            raise EvidencePublicationError("Written publication contains a symlink")
        if not entry.is_file():
            continue
        relative = entry.relative_to(directory).as_posix()
        if relative == _PUBLICATION_NAME:
            continue
        data = entry.read_bytes()
        files.append({"path": relative, "sha256": sha256(data).hexdigest(), "size": len(data)})
    files.sort(key=lambda item: cast(str, item["path"]))
    payload = {"schema_version": 1, "files": files}
    record = {**payload, "root_sha256": sha256(_canonical_json_bytes(payload)).hexdigest()}
    (directory / _PUBLICATION_NAME).write_bytes(_canonical_json_bytes(record))


def _validate_publication_root(directory: Path) -> dict[str, tuple[str, int]]:
    root = directory / _PUBLICATION_NAME
    if _contains_symlink(root, directory):
        raise EvidenceNotFoundError("Stored evidence is inconsistent")
    try:
        raw_root = root.read_bytes()
        value: object = json.loads(raw_root)
    except (OSError, json.JSONDecodeError) as error:
        raise EvidenceNotFoundError("Stored evidence is inconsistent") from error
    if not isinstance(value, dict):
        raise EvidenceNotFoundError("Stored evidence is inconsistent")
    record = cast(dict[str, object], value)
    if set(record) != {"schema_version", "files", "root_sha256"}:
        raise EvidenceNotFoundError("Stored evidence is inconsistent")
    files_value = record["files"]
    root_digest = record["root_sha256"]
    if record["schema_version"] != 1 or not isinstance(files_value, list):
        raise EvidenceNotFoundError("Stored evidence is inconsistent")
    payload: dict[str, object] = {"schema_version": 1, "files": files_value}
    if (
        not isinstance(root_digest, str)
        or re.fullmatch(r"[0-9a-f]{64}", root_digest) is None
        or sha256(_canonical_json_bytes(payload)).hexdigest() != root_digest
        or raw_root != _canonical_json_bytes(record)
    ):
        raise EvidenceNotFoundError("Stored evidence is inconsistent")

    files: dict[str, tuple[str, int]] = {}
    for item in cast(list[object], files_value):
        if not isinstance(item, dict):
            raise EvidenceNotFoundError("Stored evidence is inconsistent")
        file_record = cast(dict[str, object], item)
        if set(file_record) != {"path", "sha256", "size"}:
            raise EvidenceNotFoundError("Stored evidence is inconsistent")
        path = file_record["path"]
        digest = file_record["sha256"]
        size = file_record["size"]
        if (
            not isinstance(path, str)
            or not _is_safe_publication_path(path)
            or path in files
            or not isinstance(digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            or isinstance(size, bool)
            or not isinstance(size, int)
            or size < 0
        ):
            raise EvidenceNotFoundError("Stored evidence is inconsistent")
        target = directory / path
        if _contains_symlink(target, directory):
            raise EvidenceNotFoundError("Stored evidence is inconsistent")
        try:
            data = target.read_bytes()
        except OSError as error:
            raise EvidenceNotFoundError("Stored evidence is inconsistent") from error
        if len(data) != size or sha256(data).hexdigest() != digest:
            raise EvidenceNotFoundError("Stored evidence is inconsistent")
        files[path] = (digest, size)

    if [item["path"] for item in cast(list[dict[str, object]], files_value)] != sorted(files):
        raise EvidenceNotFoundError("Stored evidence is inconsistent")

    actual_files: set[str] = set()
    for entry in directory.rglob("*"):
        if entry.is_symlink():
            raise EvidenceNotFoundError("Stored evidence is inconsistent")
        if entry.is_file():
            actual_files.add(entry.relative_to(directory).as_posix())
    if actual_files != {*files, _PUBLICATION_NAME}:
        raise EvidenceNotFoundError("Stored evidence is inconsistent")
    return files


def _page_record(page: PageEvidence) -> dict[str, object]:
    """Produce the JSON-compatible representation used for one page record."""
    record = cast(dict[str, object], json.loads(json.dumps(asdict(page))))
    for key in ("elements", "width", "height"):
        if record[key] in (None, []):
            del record[key]
    return record


def _extraction_record(extraction: Extraction) -> dict[str, object]:
    return {
        "parser": extraction.parser,
        "warnings": list(extraction.warnings),
        "assets": [
            {"path": asset.path, "sha256": sha256(asset.data).hexdigest(), "size": len(asset.data)}
            for asset in extraction.assets
        ],
    }


def _elements(value: object) -> tuple[ElementEvidence, ...]:
    if not isinstance(value, list):
        raise ValueError("Invalid elements")
    result: list[ElementEvidence] = []
    for item in cast(list[object], value):
        if not isinstance(item, dict):
            raise ValueError("Invalid element")
        record = cast(dict[str, object], item)
        raw_regions = record["regions"]
        if not isinstance(raw_regions, list):
            raise ValueError("Invalid regions")
        result.append(
            ElementEvidence(
                element_id=_required_string(record["element_id"]),
                kind=_required_string(record["kind"]),
                text=_required_string(record["text"]),
                section=_optional_string(record["section"]),
                content_layer=_required_string(record["content_layer"]),
                regions=tuple(_region(region) for region in cast(list[object], raw_regions)),
            )
        )
    return tuple(result)


def _optional_number(value: object) -> float | None:
    return None if value is None else _number(value)


def _optional_string(value: object) -> str | None:
    if value is None or isinstance(value, str):
        return value
    raise ValueError("Expected a string or null")


def _required_string(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Expected a string")
    return value


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
