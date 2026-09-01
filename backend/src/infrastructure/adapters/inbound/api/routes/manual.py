"""Registered manual, immutable PDF, and page-evidence routes."""

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from application.ports.outbound.evidence_repository import EvidenceRepository
from application.services.citations import resolve_citations
from domain.models.document import DocumentManifest
from infrastructure.adapters.inbound.api.schemas.evidence import (
    EvidenceResponse,
    ManualResponse,
)
from infrastructure.adapters.outbound.evidence_repository.filesystem_repository import (
    EvidenceNotFoundError,
    FilesystemEvidenceRepository,
)

_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class RegisteredSource:
    """A verified immutable PDF path bound to its content manifest."""

    path: Path
    manifest: DocumentManifest


def load_registered_sources(root: Path, parser: str) -> dict[str, RegisteredSource]:
    """Build a source catalog only from complete publications verified by the repository."""

    if root.is_symlink() or not root.is_dir():
        return {}
    repository = FilesystemEvidenceRepository(root, parser)
    catalog: dict[str, RegisteredSource] = {}
    try:
        candidates = tuple(root.iterdir())
    except OSError:
        return catalog
    for hash_directory in candidates:
        if (
            _SHA256_PATTERN.fullmatch(hash_directory.name) is None
            or hash_directory.is_symlink()
            or not hash_directory.is_dir()
        ):
            continue
        publication = hash_directory / parser
        manifest_path = publication / "manifest.json"
        source_path = publication / "original.pdf"
        if (
            publication.is_symlink()
            or manifest_path.is_symlink()
            or source_path.is_symlink()
            or not manifest_path.is_file()
            or not source_path.is_file()
        ):
            continue
        try:
            manifest = _read_manifest(manifest_path)
            if manifest.sha256 != hash_directory.name:
                continue
            first_page = repository.get(f"{manifest.document_id}:page:1")
            if first_page.document_hash != manifest.sha256:
                continue
            resolved_publication = publication.resolve(strict=True)
            resolved_source = source_path.resolve(strict=True)
            if resolved_source.parent != resolved_publication:
                continue
        except EvidenceNotFoundError, OSError, ValueError, json.JSONDecodeError:
            continue
        catalog[manifest.sha256] = RegisteredSource(resolved_source, manifest)
    return catalog


def build_manual_router(
    *,
    catalog: Mapping[str, RegisteredSource],
    repository: EvidenceRepository,
    active_version: str | None,
) -> APIRouter:
    """Bind manual routes to an internal catalog and one explicit evidence repository."""

    router = APIRouter(prefix="/api/v1/manual", tags=["manual"])

    def get_manual() -> ManualResponse:
        record = catalog.get(active_version) if active_version is not None else None
        if record is None:
            raise HTTPException(status_code=404, detail="Active manual not found")
        manifest = record.manifest
        return ManualResponse(
            document_id=manifest.document_id,
            version=manifest.sha256,
            filename=manifest.filename,
            page_count=manifest.page_count,
            pdf_url=f"/api/v1/manual/pdf?version={manifest.sha256}",
        )

    def get_pdf(version: str) -> FileResponse:
        record = catalog.get(version)
        if record is None:
            raise HTTPException(status_code=404, detail="Document version not found")
        return FileResponse(
            record.path,
            media_type="application/pdf",
            filename=record.manifest.filename,
            content_disposition_type="inline",
        )

    def get_evidence(evidence_id: str) -> EvidenceResponse:
        try:
            page = resolve_citations((evidence_id,), repository)[0]
        except (EvidenceNotFoundError, IndexError) as error:
            raise HTTPException(status_code=404, detail="Evidence not found") from error
        if page.document_hash not in catalog:
            raise HTTPException(status_code=404, detail="Evidence not found")
        return EvidenceResponse.from_domain(page)

    router.add_api_route("", get_manual, methods=["GET"], response_model=ManualResponse)
    router.add_api_route("/pdf", get_pdf, methods=["GET"], response_class=FileResponse)
    router.add_api_route(
        "/evidence/{evidence_id}",
        get_evidence,
        methods=["GET"],
        response_model=EvidenceResponse,
    )
    return router


def _read_manifest(path: Path) -> DocumentManifest:
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Manifest must be an object")
    record = cast(dict[str, object], raw)
    if set(record) != {"document_id", "sha256", "filename", "page_count"}:
        raise ValueError("Manifest fields are invalid")
    document_id = record["document_id"]
    digest = record["sha256"]
    filename = record["filename"]
    page_count = record["page_count"]
    if (
        not isinstance(document_id, str)
        or not isinstance(digest, str)
        or _SHA256_PATTERN.fullmatch(digest) is None
        or document_id != f"sha256:{digest}"
        or not isinstance(filename, str)
        or not filename
        or type(page_count) is not int
        or page_count <= 0
    ):
        raise ValueError("Manifest identity is invalid")
    return DocumentManifest(document_id, digest, filename, page_count)
