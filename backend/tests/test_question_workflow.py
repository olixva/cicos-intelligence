"""Grounded document-question workflow contracts."""

import asyncio

import pytest
from fakes import FailingLanguageModel, FakeEvidenceRepository, FakeLanguageModel, FakeRetriever

from application.models.query import AnswerBlock, QueryInput, QuestionAnswer
from application.models.retrieval import Chunk
from application.ports.outbound.language_model import LanguageModelError
from domain.models.evidence import PageEvidence


def _page(evidence_id: str = "manual:page:7") -> PageEvidence:
    return PageEvidence(
        evidence_id=evidence_id,
        document_hash="a" * 64,
        pdf_page=7,
        text="Texto completo que no debe enviarse al modelo.",
        printed_label="7",
        image_path="pages/7.png",
        regions=(),
    )


def test_provider_citation_not_delivered_in_context_is_rejected() -> None:
    """A fabricated source ID must never survive as a valid citation."""
    from infrastructure.adapters.outbound.question_workflow.langgraph_workflow import (
        LangGraphQuestionWorkflow,
    )

    async def scenario() -> None:
        page = _page()
        retriever = FakeRetriever((Chunk("chunk-7", "Fragmento entregado.", (page.evidence_id,)),))
        model = FakeLanguageModel(
            QuestionAnswer(
                status="answered",
                blocks=(AnswerBlock("Respuesta inventada.", ("manual:page:999",)),),
            )
        )
        workflow = LangGraphQuestionWorkflow(
            retriever=retriever,
            evidence_repository=FakeEvidenceRepository((page,)),
            language_model=model,
        )

        execution = await workflow.run(QueryInput("¿Qué indica el manual?", "es"))

        assert execution.result == QuestionAnswer("insufficient_evidence", ())
        assert tuple(item.evidence_id for item in execution.context) == (page.evidence_id,)
        assert execution.context[0].text == "Fragmento entregado."
        assert execution.context[0].source.text != execution.context[0].text

    asyncio.run(scenario())


def test_provider_technical_error_is_not_converted_to_insufficient_evidence() -> None:
    """Masking an outage as a grounded answer would corrupt availability evaluation."""
    from infrastructure.adapters.outbound.question_workflow.langgraph_workflow import (
        LangGraphQuestionWorkflow,
    )

    async def scenario() -> None:
        page = _page()
        workflow = LangGraphQuestionWorkflow(
            retriever=FakeRetriever(
                (Chunk("chunk-7", "Fragmento entregado.", (page.evidence_id,)),)
            ),
            evidence_repository=FakeEvidenceRepository((page,)),
            language_model=FailingLanguageModel(),
        )

        with pytest.raises(LanguageModelError, match="transport failed"):
            await workflow.run(QueryInput("¿Qué indica el manual?", "es"))

    asyncio.run(scenario())


def test_mixed_supported_and_fabricated_citations_are_downgraded_to_partial() -> None:
    """Keeping an answered status after removing a fabricated citation would overstate grounding."""
    from infrastructure.adapters.outbound.question_workflow.langgraph_workflow import (
        LangGraphQuestionWorkflow,
    )

    async def scenario() -> None:
        page = _page()
        model = FakeLanguageModel(
            QuestionAnswer(
                "answered",
                (
                    AnswerBlock(
                        "Respuesta parcialmente apoyada.",
                        (page.evidence_id, "manual:page:999"),
                    ),
                ),
            )
        )
        workflow = LangGraphQuestionWorkflow(
            retriever=FakeRetriever(
                (Chunk("chunk-7", "Fragmento entregado.", (page.evidence_id,)),)
            ),
            evidence_repository=FakeEvidenceRepository((page,)),
            language_model=model,
        )

        execution = await workflow.run(QueryInput("¿Qué indica el manual?", "es"))

        assert execution.result == QuestionAnswer(
            "partial",
            (AnswerBlock("Respuesta parcialmente apoyada.", (page.evidence_id,)),),
        )

    asyncio.run(scenario())


def test_empty_retrieval_returns_insufficient_evidence_without_calling_model() -> None:
    """Paying for generation without context could only produce an ungrounded answer."""
    from infrastructure.adapters.outbound.question_workflow.langgraph_workflow import (
        LangGraphQuestionWorkflow,
    )

    async def scenario() -> None:
        model = FakeLanguageModel(
            QuestionAnswer("answered", (AnswerBlock("No debe usarse.", ("unknown",)),))
        )
        workflow = LangGraphQuestionWorkflow(
            retriever=FakeRetriever(()),
            evidence_repository=FakeEvidenceRepository(()),
            language_model=model,
        )

        execution = await workflow.run(QueryInput("¿Qué indica el manual?", "es"))

        assert execution.result == QuestionAnswer("insufficient_evidence", ())
        assert execution.context == ()
        assert model.calls == []

    asyncio.run(scenario())


def test_answer_question_use_case_preserves_workflow_execution() -> None:
    """Rebuilding an execution in the use case could lose its effective context or trace ID."""
    from application.models.query import ContextEvidence, QueryExecution
    from application.use_cases.answer_question_use_case import AnswerQuestionUseCase

    class Workflow:
        async def run(self, query: QueryInput) -> QueryExecution:
            page = _page()
            context = (ContextEvidence(page.evidence_id, "Fragmento.", page),)
            return QueryExecution(
                QuestionAnswer("answered", (AnswerBlock("Respuesta.", (page.evidence_id,)),)),
                context,
                "trace-123",
            )

    async def scenario() -> None:
        result = await AnswerQuestionUseCase(Workflow()).execute(QueryInput("Pregunta", "es"))
        assert result.trace_id == "trace-123"
        assert result.context[0].text == "Fragmento."

    asyncio.run(scenario())
