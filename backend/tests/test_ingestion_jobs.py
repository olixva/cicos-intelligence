from __future__ import annotations

from datetime import UTC, datetime

import pytest

from application.models.ingestion import (
    IngestionAlreadyRunning,
    IngestionEvent,
    IngestionJobStore,
    IngestionSnapshot,
)


def test_store_starts_and_persists_one_running_job(tmp_path) -> None:
    store = IngestionJobStore(tmp_path / "ingestion.json")

    initial = store.load()
    assert isinstance(initial, IngestionSnapshot)
    assert initial.active_job is None

    job = store.start()
    assert job.status == "running"
    assert job.stage == "verifying_manual"

    reloaded = IngestionJobStore(tmp_path / "ingestion.json").load()
    assert reloaded.active_job is not None
    assert reloaded.active_job.job_id == job.job_id

    with pytest.raises(IngestionAlreadyRunning):
        store.start()


def test_store_appends_public_event_and_marks_terminal_job(tmp_path) -> None:
    store = IngestionJobStore(tmp_path / "ingestion.json")
    job = store.start()
    event = IngestionEvent(
        event_id="evt-1",
        job_id=job.job_id,
        timestamp=datetime.now(UTC),
        stage="extracting_evidence",
        status="running",
        data={"pages": 111},
    )

    store.append_event(job.job_id, event)
    completed = store.update(
        job.job_id,
        status="succeeded",
        stage="published_index",
        pages=111,
        chunks=118,
        collection="allianz-test",
    )

    assert completed.status == "succeeded"
    assert completed.events == (event,)
    assert store.load().active_job is None
    assert store.load().last_job == completed
