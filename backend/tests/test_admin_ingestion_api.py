from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from application.models.ingestion import IngestionJobStore


def test_admin_ingestion_starts_one_background_job_and_exposes_snapshot(tmp_path: Path) -> None:
    from application.services.ingestion_jobs import IngestionJobService
    from infrastructure.adapters.inbound.api.app import create_app

    store = IngestionJobStore(tmp_path / "ingestion.json")
    service = IngestionJobService(store)
    started: list[str] = []

    async def runner(job_id: str) -> None:
        started.append(job_id)

    app = create_app(admin_ingestion_service=service, admin_ingestion_runner=runner)
    with TestClient(app) as client:
        assert client.get("/api/v1/admin/ingestion").json()["active_job"] is None
        response = client.post("/api/v1/admin/ingestion")
        assert response.status_code == 202
        job_id = response.json()["job_id"]
        assert response.json()["status"] == "running"
        assert client.get("/api/v1/admin/ingestion").json()["active_job"]["job_id"] == job_id
        assert client.post("/api/v1/admin/ingestion").status_code == 409
    assert started == [job_id]


def test_admin_ingestion_events_emit_persisted_terminal_event(tmp_path: Path) -> None:
    from datetime import UTC, datetime

    from application.models.ingestion import IngestionEvent
    from application.services.ingestion_jobs import IngestionJobService
    from infrastructure.adapters.inbound.api.app import create_app

    store = IngestionJobStore(tmp_path / "ingestion.json")
    service = IngestionJobService(store)
    job = service.start()
    store.append_event(
        job.job_id,
        IngestionEvent(
            event_id="evt-terminal",
            job_id=job.job_id,
            timestamp=datetime.now(UTC),
            stage="published_index",
            status="succeeded",
            data={"chunks": 118},
        ),
    )
    store.update(job.job_id, status="succeeded", stage="published_index")
    app = create_app(admin_ingestion_service=service)

    with TestClient(app) as client:
        response = client.get("/api/v1/admin/ingestion/events")
    assert response.status_code == 200
    assert "evt-terminal" in response.text
    assert '"status": "succeeded"' in response.text


def test_admin_ingestion_extractions_returns_only_public_page_summary(tmp_path: Path) -> None:
    from domain.models.evidence import PageEvidence
    from infrastructure.adapters.inbound.api.app import create_app

    class Repository:
        def get_document_pages(self, document_hash: str) -> tuple[PageEvidence, ...]:
            return (
                PageEvidence(
                    evidence_id=f"sha256:{document_hash}:page:1",
                    document_hash=document_hash,
                    pdf_page=1,
                    text="Texto extraído del manual.",
                    printed_label="1",
                    image_path="private/path.png",
                    regions=((1.0, 2.0, 3.0, 4.0),),
                ),
            )

    app = create_app(
        admin_ingestion_service=None,
        admin_ingestion_repository=Repository(),
        admin_ingestion_document_hash="a" * 64,
    )
    with TestClient(app) as client:
        response = client.get("/api/v1/admin/ingestion/extractions?offset=0&limit=1")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["pdf_page"] == 1
    assert body["items"][0]["regions_available"] is True
    assert "image_path" not in response.text
