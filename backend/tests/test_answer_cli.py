"""Technical CLI adapter for the document-question use case."""

import json
from pathlib import Path

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
                (ContextEvidence((page.evidence_id,), "Fragmento efectivo.", (page,)),),
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
                "evidence_ids": ["manual:page:7"],
                "sources": [
                    {
                        "evidence_id": "manual:page:7",
                        "image_path": "pages/7.png",
                        "pdf_page": 7,
                        "printed_label": "7",
                    }
                ],
                "text": "Fragmento efectivo.",
            }
        ],
        "status": "answered",
        "trace_id": "trace-123",
    }
    assert "OPENAI_API_KEY" not in captured.out


def test_answer_composition_fails_before_io_when_langfuse_configuration_is_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Missing local observability settings must not fall through to cloud or unrelated IO."""
    from bootstrap import build_answer_question

    for name in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ALLIANZ_EVIDENCE_ROOT", str(tmp_path / "does-not-exist"))

    with pytest.raises(
        ValueError,
        match="LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_BASE_URL",
    ):
        build_answer_question("structured")


def test_answer_command_reports_workflow_timeout_without_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    """A graph timeout must remain a concise technical CLI error."""
    from infrastructure.adapters.inbound.cli import main as cli
    from infrastructure.adapters.outbound.question_workflow.langgraph_workflow import (
        QuestionWorkflowTimeoutError,
    )

    class UseCase:
        async def execute(self, query: QueryInput) -> QueryExecution:
            del query
            raise QuestionWorkflowTimeoutError("question workflow timed out")

    def build(profile: str) -> UseCase:
        assert profile == "structured"
        return UseCase()

    monkeypatch.setattr(cli, "build_answer_question", build)

    result = cli.main(["answer", "--text", "¿Qué indica?", "--profile", "structured"])

    captured = capsys.readouterr()
    assert result == 2
    assert captured.out == ""
    assert "question workflow timed out" in captured.err
    assert "Traceback" not in captured.err
