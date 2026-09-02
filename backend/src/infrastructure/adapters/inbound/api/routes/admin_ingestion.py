"""HTTP control surface for the local, manual-only ingestion job."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from application.models.ingestion import (
    IngestionAlreadyRunning,
    IngestionEvent,
    IngestionJob,
    IngestionSnapshot,
)
from application.ports.outbound.evidence_repository import EvidenceRepository
from application.services.ingestion_jobs import IngestionJobService

IngestionRunner = Callable[[str], Awaitable[None]]


def build_admin_ingestion_router(
    *,
    service: IngestionJobService | None,
    runner: IngestionRunner | None = None,
    evidence_repository: EvidenceRepository | None = None,
    document_hash: str | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/admin/ingestion", tags=["admin-ingestion"])

    def get_snapshot() -> dict[str, object]:
        if service is None:
            raise HTTPException(
                status_code=503, detail="La administración de ingesta no está disponible."
            )
        return _snapshot_payload(service.snapshot())

    async def start_ingestion() -> JSONResponse:
        if service is None or runner is None:
            raise HTTPException(
                status_code=503, detail="La ingesta administrativa no está disponible."
            )
        try:
            job = service.start()
        except IngestionAlreadyRunning as error:
            raise HTTPException(status_code=409, detail="Ya hay una ingesta en curso.") from error
        asyncio.ensure_future(runner(job.job_id))
        return JSONResponse(status_code=202, content=_job_payload(job))

    async def ingestion_events():
        try:
            from sse_starlette.sse import EventSourceResponse
        except ImportError as error:
            raise HTTPException(
                status_code=503, detail="Los eventos de ingesta no están disponibles."
            ) from error

        async def events():
            emitted = 0
            while True:
                if service is None:
                    return
                snapshot = service.snapshot()
                job = snapshot.active_job or snapshot.last_job
                if job is None:
                    return
                for event in job.events[emitted:]:
                    emitted += 1
                    yield _event_payload(event)
                if snapshot.active_job is None:
                    return
                await asyncio.sleep(0.2)

        return EventSourceResponse(events())

    def get_extractions(offset: int = 0, limit: int = 50) -> dict[str, object]:
        if evidence_repository is None or document_hash is None:
            raise HTTPException(status_code=503, detail="Las extracciones no están disponibles.")
        if offset < 0 or limit < 1 or limit > 200:
            raise HTTPException(status_code=422, detail="Paginación inválida.")
        pages = evidence_repository.get_document_pages(document_hash)
        items = [
            {
                "evidence_id": page.evidence_id,
                "document_hash": page.document_hash,
                "pdf_page": page.pdf_page,
                "printed_label": page.printed_label,
                "text_preview": page.text[:240],
                "regions_available": bool(page.regions),
                "pdf_url": f"/api/v1/manual/pdf?version={page.document_hash}",
            }
            for page in pages[offset : offset + limit]
        ]
        return {"total": len(pages), "offset": offset, "limit": limit, "items": items}

    router.add_api_route("", get_snapshot, methods=["GET"])
    router.add_api_route("", start_ingestion, methods=["POST"], status_code=202)
    router.add_api_route("/events", ingestion_events, methods=["GET"])
    router.add_api_route("/extractions", get_extractions, methods=["GET"])
    return router


def _snapshot_payload(snapshot: IngestionSnapshot) -> dict[str, object]:
    return {
        "active_job": _job_payload(snapshot.active_job) if snapshot.active_job else None,
        "last_job": _job_payload(snapshot.last_job) if snapshot.last_job else None,
    }


def _job_payload(job: IngestionJob) -> dict[str, object]:
    return {
        "job_id": job.job_id,
        "status": job.status,
        "stage": job.stage,
        "started_at": job.started_at.isoformat(),
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "document_hash": job.document_hash,
        "parser": job.parser,
        "pages": job.pages,
        "chunks": job.chunks,
        "collection": job.collection,
        "error": job.error,
        "events": [_event_payload(event) for event in job.events],
    }


def _event_payload(event: IngestionEvent) -> dict[str, object]:
    return {
        "event": "ingestion",
        "id": event.event_id,
        "data": json.dumps(
            {
                "event_id": event.event_id,
                "job_id": event.job_id,
                "timestamp": event.timestamp.isoformat(),
                "stage": event.stage,
                "status": event.status,
                "data": event.data,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
    }
