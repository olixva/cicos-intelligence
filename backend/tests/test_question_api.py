"""HTTP contract for the explicit document-question route."""

from dataclasses import dataclass

from fastapi.testclient import TestClient

from application.models.query import (
    AnswerBlock,
    ContextEvidence,
    QueryExecution,
    QueryInput,
    QuestionAnswer,
)
from domain.models.evidence import PageEvidence


@dataclass(frozen=True, slots=True)
class _FakeAnswerQuestion:
    execution: QueryExecution
    received: list[QueryInput]

    async def execute(self, query: QueryInput) -> QueryExecution:
        self.received.append(query)
        return self.execution


def test_question_route_returns_the_grounded_execution_from_the_inbound_port() -> None:
    """Dropping context or trace data would make an answer impossible to audit."""
    from infrastructure.adapters.inbound.api.app import create_app

    page = PageEvidence(
        evidence_id="sha256:abc:page:5",
        document_hash="abc",
        pdf_page=5,
        text="Texto de la página.",
        printed_label="3",
        image_path="pages/5.png",
        regions=(),
    )
    execution = QueryExecution(
        result=QuestionAnswer(
            "answered",
            (AnswerBlock("La respuesta.", (page.evidence_id,)),),
        ),
        context=(
            ContextEvidence(
                evidence_ids=(page.evidence_id,),
                text="Texto de la página.",
                sources=(page,),
                delivery="text",
            ),
        ),
        trace_id="trace-123",
    )
    received: list[QueryInput] = []
    client = TestClient(create_app(answer_question=_FakeAnswerQuestion(execution, received)))

    response = client.post(
        "/api/v1/questions/answer",
        json={"text": "¿Qué dice el manual?", "language": "en"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "answered",
        "blocks": [{"text": "La respuesta.", "evidence_ids": ["sha256:abc:page:5"]}],
        "context": [
            {
                "evidence_ids": ["sha256:abc:page:5"],
                "text": "Texto de la página.",
                "delivery": "text",
                "sources": [
                    {
                        "evidence_id": "sha256:abc:page:5",
                        "document_hash": "abc",
                        "pdf_page": 5,
                        "printed_label": "3",
                    }
                ],
            }
        ],
        "trace_id": "trace-123",
    }
    assert received == [QueryInput("¿Qué dice el manual?", "en")]


def test_question_route_defaults_the_question_language_to_spanish() -> None:
    """Ignoring the transport default would change the model's answer language."""
    from infrastructure.adapters.inbound.api.app import create_app

    received: list[QueryInput] = []
    execution = QueryExecution(QuestionAnswer("insufficient_evidence", ()), ())
    client = TestClient(create_app(answer_question=_FakeAnswerQuestion(execution, received)))

    response = client.post("/api/v1/questions/answer", json={"text": "Pregunta"})

    assert response.status_code == 200
    assert response.json() == {
        "status": "insufficient_evidence",
        "blocks": [],
        "context": [],
        "trace_id": None,
    }
    assert received == [QueryInput("Pregunta", "es")]


def test_question_route_rejects_invalid_input_before_calling_the_use_case() -> None:
    """Passing blank text or an unsupported language to the workflow is an API contract bug."""
    from infrastructure.adapters.inbound.api.app import create_app

    received: list[QueryInput] = []
    execution = QueryExecution(QuestionAnswer("insufficient_evidence", ()), ())
    client = TestClient(create_app(answer_question=_FakeAnswerQuestion(execution, received)))

    blank = client.post("/api/v1/questions/answer", json={"text": "   "})
    unsupported_language = client.post(
        "/api/v1/questions/answer",
        json={"text": "Question", "language": "fr"},
    )

    assert blank.status_code == 422
    assert unsupported_language.status_code == 422
    assert received == []


def test_question_route_keeps_provider_failures_as_technical_errors() -> None:
    """Converting provider failures into insufficient evidence would hide an operational outage."""
    from infrastructure.adapters.inbound.api.app import create_app

    class FailingAnswerQuestion:
        async def execute(self, query: QueryInput) -> QueryExecution:
            raise RuntimeError("provider unavailable")

    client = TestClient(
        create_app(answer_question=FailingAnswerQuestion()),
        raise_server_exceptions=False,
    )

    response = client.post("/api/v1/questions/answer", json={"text": "Pregunta"})

    assert response.status_code == 500
