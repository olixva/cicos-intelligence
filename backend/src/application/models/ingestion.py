"""Public values for the local administrator ingestion job."""

from __future__ import annotations

import json
import os
import threading
import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

type IngestionStatus = Literal["running", "succeeded", "failed"]
type IngestionStage = Literal[
    "verifying_manual", "extracting_evidence", "publishing_index", "published_index"
]
type EventData = dict[str, str | int | None]


@dataclass(frozen=True, slots=True)
class IngestionEvent:
    event_id: str
    job_id: str
    timestamp: datetime
    stage: IngestionStage
    status: IngestionStatus
    data: EventData = field(default_factory=lambda: {})


@dataclass(frozen=True, slots=True)
class IngestionJob:
    job_id: str
    status: IngestionStatus
    stage: IngestionStage
    started_at: datetime
    finished_at: datetime | None = None
    document_hash: str | None = None
    parser: str | None = None
    pages: int | None = None
    chunks: int | None = None
    collection: str | None = None
    error: str | None = None
    events: tuple[IngestionEvent, ...] = ()


@dataclass(frozen=True, slots=True)
class IngestionSnapshot:
    active_job: IngestionJob | None
    last_job: IngestionJob | None = None


class IngestionAlreadyRunning(RuntimeError):
    """Raised when an administrator tries to start a second job."""


class IngestionJobStore:
    """Small atomic JSON store suitable for one local application process."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def load(self) -> IngestionSnapshot:
        with self._lock:
            return self._read()

    def start(self) -> IngestionJob:
        with self._lock:
            snapshot = self._read()
            if snapshot.active_job is not None:
                raise IngestionAlreadyRunning(snapshot.active_job.job_id)
            job = IngestionJob(
                job_id=str(uuid.uuid4()),
                status="running",
                stage="verifying_manual",
                started_at=datetime.now(UTC),
            )
            self._write(IngestionSnapshot(active_job=job, last_job=snapshot.last_job))
            return job

    def update(self, job_id: str, **changes: object) -> IngestionJob:
        with self._lock:
            snapshot = self._read()
            job = snapshot.active_job or snapshot.last_job
            if job is None or job.job_id != job_id:
                raise KeyError(job_id)
            allowed = {
                "status",
                "stage",
                "finished_at",
                "document_hash",
                "parser",
                "pages",
                "chunks",
                "collection",
                "error",
            }
            unknown = set(changes) - allowed
            if unknown:
                raise ValueError(f"unsupported ingestion fields: {', '.join(sorted(unknown))}")
            updated = replace(job, **changes)
            active = None if updated.status in ("succeeded", "failed") else updated
            self._write(IngestionSnapshot(active_job=active, last_job=updated))
            return updated

    def append_event(self, job_id: str, event: IngestionEvent) -> IngestionEvent:
        with self._lock:
            snapshot = self._read()
            job = snapshot.active_job
            if job is None or job.job_id != job_id or event.job_id != job_id:
                raise KeyError(job_id)
            updated = replace(job, events=(*job.events, event), stage=event.stage)
            self._write(IngestionSnapshot(active_job=updated, last_job=snapshot.last_job))
            return event

    def _read(self) -> IngestionSnapshot:
        if not self.path.exists():
            return IngestionSnapshot(active_job=None)
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return IngestionSnapshot(active_job=None)
            return _snapshot_from_json(cast(dict[str, object], raw))
        except OSError, ValueError, TypeError, KeyError:
            return IngestionSnapshot(active_job=None)

    def _write(self, snapshot: IngestionSnapshot) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(
            json.dumps(_snapshot_to_json(snapshot), sort_keys=True), encoding="utf-8"
        )
        os.replace(temporary, self.path)


def _snapshot_to_json(snapshot: IngestionSnapshot) -> dict[str, object]:
    return {
        "active_job": _job_to_json(snapshot.active_job),
        "last_job": _job_to_json(snapshot.last_job),
    }


def _job_to_json(job: IngestionJob | None) -> dict[str, object] | None:
    if job is None:
        return None
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
        "events": [_event_to_json(event) for event in job.events],
    }


def _event_to_json(event: IngestionEvent) -> dict[str, object]:
    return {
        "event_id": event.event_id,
        "job_id": event.job_id,
        "timestamp": event.timestamp.isoformat(),
        "stage": event.stage,
        "status": event.status,
        "data": event.data,
    }


def _snapshot_from_json(raw: dict[str, object]) -> IngestionSnapshot:
    active_raw = raw.get("active_job")
    last_raw = raw.get("last_job")
    return IngestionSnapshot(
        active_job=_job_from_json(cast(dict[str, object], active_raw))
        if isinstance(active_raw, dict)
        else None,
        last_job=_job_from_json(cast(dict[str, object], last_raw))
        if isinstance(last_raw, dict)
        else None,
    )


def _job_from_json(raw: dict[str, object]) -> IngestionJob:
    events_raw = raw.get("events", [])
    raw_items = cast(list[object], events_raw) if isinstance(events_raw, list) else []
    events = tuple(
        _event_from_json(cast(dict[str, object], item))
        for item in raw_items
        if isinstance(item, dict)
    )
    return IngestionJob(
        job_id=_required_str(raw, "job_id"),
        status=cast(IngestionStatus, _required_str(raw, "status")),
        stage=cast(IngestionStage, _required_str(raw, "stage")),
        started_at=datetime.fromisoformat(_required_str(raw, "started_at")),
        finished_at=_optional_datetime(raw.get("finished_at")),
        document_hash=_optional_str(raw.get("document_hash")),
        parser=_optional_str(raw.get("parser")),
        pages=_optional_int(raw.get("pages")),
        chunks=_optional_int(raw.get("chunks")),
        collection=_optional_str(raw.get("collection")),
        error=_optional_str(raw.get("error")),
        events=events,
    )


def _event_from_json(raw: dict[str, object]) -> IngestionEvent:
    data = raw.get("data")
    return IngestionEvent(
        event_id=_required_str(raw, "event_id"),
        job_id=_required_str(raw, "job_id"),
        timestamp=datetime.fromisoformat(_required_str(raw, "timestamp")),
        stage=cast(IngestionStage, _required_str(raw, "stage")),
        status=cast(IngestionStatus, _required_str(raw, "status")),
        data=cast(EventData, data) if isinstance(data, dict) else {},
    )


def _required_str(raw: dict[str, object], key: str) -> str:
    value = raw[key]
    if not isinstance(value, str):
        raise ValueError(key)
    return value


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _optional_datetime(value: object) -> datetime | None:
    return datetime.fromisoformat(value) if isinstance(value, str) else None
