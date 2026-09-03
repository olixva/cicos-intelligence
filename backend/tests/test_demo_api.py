from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from infrastructure.adapters.inbound.api.routes.demo import DEFAULT_DEMO_CASE_IDS, build_demo_router


def test_default_demo_catalogue_covers_the_five_demonstration_outcomes() -> None:
    """La demo ordena dos preguntas y tres siniestros con desenlaces distintos."""
    assert DEFAULT_DEMO_CASE_IDS == (
        "consulta-es-01-alcoholemia",
        "consulta-synth-21-atestado-ascide-cierra",
        "siniestro-synth-12-b9-marcha-atras",
        "accident-02-pile-up-es",
        "accident-04-lane-change-es",
    )


def test_demo_cases_expose_only_safe_development_fields(tmp_path: Path) -> None:
    source = tmp_path / "development.jsonl"
    source.write_text(
        '{"case_id":"c1","text":"relato","language":"es","expected_intent":"claim","expected_output":"oculto"}\n',
        encoding="utf-8",
    )
    app = FastAPI()
    app.include_router(build_demo_router(source, case_ids=("c1",)))
    response = TestClient(app).get("/api/v1/demo/cases")
    assert response.status_code == 200
    assert response.json() == [
        {"case_id": "c1", "text": "relato", "language": "es", "expected_intent": "claim"}
    ]


def test_demo_cases_expose_only_safe_fields_from_full_golden_schema(tmp_path: Path) -> None:
    """The real development.jsonl holds full GoldenDatasetItem records; only input/metadata
    fields the product may show publicly are forwarded, never expected_output or review."""
    source = tmp_path / "development.jsonl"
    source.write_text(
        '{"input":{"text":"relato","language":"es","clarifications":[]},'
        '"expected_output":{"reference":"secreto","decisions":{"intent":"claim"},'
        '"requirements":[{"requirement_id":"r1","description":"oculto"}],'
        '"acceptable_alternatives":[],"forbidden_facts":[],"evidence_requirements":[]},'
        '"metadata":{"case_id":"c1","family_id":"c1","partition":"development",'
        '"review_status":"adjudicated","provenance":{"kind":"interview_example",'
        '"source_ids":["x"]},"language":"es","expected_intent":"claim",'
        '"review":{"reviewer_ids":["r"],"independent_resolution_checked":true,'
        '"evidence_checked":true,"adversarial_checked":true,"adjudication_note":"n",'
        '"open_discrepancies":[]}}}\n',
        encoding="utf-8",
    )
    app = FastAPI()
    app.include_router(build_demo_router(source, case_ids=("c1",)))
    response = TestClient(app).get("/api/v1/demo/cases")
    assert response.status_code == 200
    assert response.json() == [
        {"case_id": "c1", "text": "relato", "language": "es", "expected_intent": "claim"}
    ]
    assert "secreto" not in response.text
    assert "oculto" not in response.text


def test_demo_catalogue_is_curated_and_ordered(tmp_path: Path) -> None:
    """El conjunto de desarrollo crece con la curación; la demo no crece con él.

    Se sirven sólo los casos elegidos y en el orden pedido, y un identificador
    que ya no exista se ignora en lugar de tumbar la interfaz.
    """
    source = tmp_path / "development.jsonl"
    source.write_text(
        "\n".join(
            f'{{"case_id":"{cid}","text":"t","language":"es","expected_intent":"claim"}}'
            for cid in ("uno", "dos", "tres")
        )
        + "\n",
        encoding="utf-8",
    )
    app = FastAPI()
    app.include_router(build_demo_router(source, case_ids=("tres", "no-existe", "uno")))
    response = TestClient(app).get("/api/v1/demo/cases")

    assert response.status_code == 200
    assert [case["case_id"] for case in response.json()] == ["tres", "uno"]


def test_demo_catalogue_uses_a_described_claim_with_one_decisive_missing_fact(
    tmp_path: Path,
) -> None:
    source = tmp_path / "development.jsonl"
    source.write_text(
        '{"case_id":"siniestro-synth-12-b9-marcha-atras","text":"texto original",'
        '"language":"es","expected_intent":"claim"}\n',
        encoding="utf-8",
    )
    app = FastAPI()
    app.include_router(build_demo_router(source, case_ids=("siniestro-synth-12-b9-marcha-atras",)))

    response = TestClient(app).get("/api/v1/demo/cases")

    assert response.status_code == 200
    assert response.json()[0]["text"] == (
        "El vehículo A golpea al vehículo B mientras realiza una maniobra de marcha atrás. "
        "No hay D.A.A. ni atestado."
    )


def test_demo_catalogue_reports_unavailable_when_no_curated_case_exists(tmp_path: Path) -> None:
    source = tmp_path / "development.jsonl"
    source.write_text(
        '{"case_id":"otro","text":"t","language":"es","expected_intent":"claim"}\n',
        encoding="utf-8",
    )
    app = FastAPI()
    app.include_router(build_demo_router(source, case_ids=("no-esta",)))

    assert TestClient(app).get("/api/v1/demo/cases").status_code == 503
