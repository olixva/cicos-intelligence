"""Technical CLI adapter for the document-question use case."""

import json

import pytest
from pytest import CaptureFixture

from application.models.query import (
    AnswerBlock,
    ContextEvidence,
    QueryExecution,
    QueryInput,
    QuestionAnswer,
)
from domain.models.evidence import PageEvidence


def test_answer_command_prints_grounded_result_and_safe_execution_metadata(
    monkeypatch: pytest.MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    """The technical command must serialize effective context without exposing credentials."""
    from infrastructure.adapters.inbound.cli import main as cli

    received: list[QueryInput] = []
    page = PageEvidence(
        evidence_id="manual:page:7",
        document_hash="a" * 64,
        pdf_page=7,
        text="Texto completo no entregado.",
        printed_label="7",
        image_path="pages/7.png",
        regions=(),
    )

    class UseCase:
        async def execute(self, query: QueryInput) -> QueryExecution:
            received.append(query)
            return QueryExecution(
                QuestionAnswer("answered", (AnswerBlock("Respuesta.", (page.evidence_id,)),)),
                (ContextEvidence(page.evidence_id, "Fragmento efectivo.", page),),
                "trace-123",
            )

    def build(profile: str) -> UseCase:
        assert profile == "structured"
        return UseCase()

    monkeypatch.setattr(cli, "build_answer_question", build)

    result = cli.main(
        ["answer", "--text", "¿Qué indica?", "--profile", "structured", "--language", "es"]
    )

    captured = capsys.readouterr()
    assert result == 0
    assert captured.err == ""
    assert received == [QueryInput("¿Qué indica?", "es")]
    assert json.loads(captured.out) == {
        "blocks": [{"evidence_ids": ["manual:page:7"], "text": "Respuesta."}],
        "context": [
            {
                "delivery": "text",
                "evidence_id": "manual:page:7",
                "source": {
                    "image_path": "pages/7.png",
                    "pdf_page": 7,
                    "printed_label": "7",
                },
                "text": "Fragmento efectivo.",
            }
        ],
        "status": "answered",
        "trace_id": "trace-123",
    }
    assert "OPENAI_API_KEY" not in captured.out
