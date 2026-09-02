from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from infrastructure.adapters.inbound.api.routes.demo import build_demo_router


def test_demo_cases_expose_only_safe_development_fields(tmp_path: Path) -> None:
    source = tmp_path / "development.jsonl"
    source.write_text(
        '{"case_id":"c1","text":"relato","language":"es","expected_intent":"claim","expected_output":"oculto"}\n',
        encoding="utf-8",
    )
    app = FastAPI()
    app.include_router(build_demo_router(source))
    response = TestClient(app).get("/api/v1/demo/cases")
    assert response.status_code == 200
    assert response.json() == [
        {"case_id": "c1", "text": "relato", "language": "es", "expected_intent": "claim"}
    ]
