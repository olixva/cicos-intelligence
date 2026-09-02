"""Grounded document-question workflow contracts."""

import asyncio

import pytest
from fakes import FailingLanguageModel, FakeEvidenceRepository, FakeLanguageModel, FakeRetriever

from application.models.query import AnswerBlock, QueryInput, QuestionAnswer
from application.models.retrieval import Chunk
from application.ports.outbound.language_model import LanguageModelError
from domain.models.evidence import PageEvidence


def _page(evidence_id: str = "manual:page:7", pdf_page: int = 7) -> PageEvidence:
    return PageEvidence(
        evidence_id=evidence_id,
        document_hash="a" * 64,
        pdf_page=pdf_page,
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
        assert tuple(item.evidence_ids for item in execution.context) == ((page.evidence_id,),)
        assert execution.context[0].text == "Fragmento entregado."
        assert execution.context[0].sources[0].text != execution.context[0].text

    asyncio.run(scenario())


def test_multipage_context_requires_the_complete_source_bundle() -> None:
    """A single page cannot support text delivered only as one indivisible multipage chunk."""
    from infrastructure.adapters.outbound.question_workflow.langgraph_workflow import (
        LangGraphQuestionWorkflow,
    )

    async def scenario() -> None:
        page_7 = _page("manual:page:7", 7)
        page_8 = _page("manual:page:8", 8)
        retriever = FakeRetriever(
            (
                Chunk(
                    "chunk-7-8",
                    "Tabla que comienza en la página 7 y continúa en la página 8.",
                    (page_7.evidence_id, page_8.evidence_id),
                ),
            )
        )
        model = FakeLanguageModel(
            QuestionAnswer(
                "answered",
                (AnswerBlock("Conclusión multipágina.", (page_7.evidence_id,)),),
            )
        )
        workflow = LangGraphQuestionWorkflow(
            retriever=retriever,
            evidence_repository=FakeEvidenceRepository((page_7, page_8)),
            language_model=model,
        )

        execution = await workflow.run(QueryInput("¿Qué indica la tabla?", "es"))

        assert execution.result == QuestionAnswer("insufficient_evidence", ())
        assert len(execution.context) == 1
        assert execution.context[0].evidence_ids == (
            page_7.evidence_id,
            page_8.evidence_id,
        )
        assert tuple(source.evidence_id for source in execution.context[0].sources) == (
            page_7.evidence_id,
            page_8.evidence_id,
        )

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
            context = (ContextEvidence((page.evidence_id,), "Fragmento.", (page,)),)
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


def _stub_workflow_fixtures(*, trace_id: str, trace_url: str | None):
    """Build the minimum stubs that drive the question workflow to a real answer."""

    from infrastructure.adapters.outbound.question_workflow.langgraph_workflow import (
        LangGraphQuestionWorkflow,
    )

    page = _page()
    chunk = Chunk(
        chunk_id="chunk-1",
        text="Fragmento.",
        evidence_ids=(page.evidence_id,),
    )
    answer = QuestionAnswer("answered", (AnswerBlock("Respuesta.", (page.evidence_id,)),))

    workflow = LangGraphQuestionWorkflow(
        retriever=FakeRetriever(chunks=(chunk,)),
        evidence_repository=FakeEvidenceRepository(pages=(page,)),
        language_model=FakeLanguageModel(answer=answer),
        trace_id_factory=lambda: trace_id,
        trace_url_factory=(lambda trace_id: trace_url) if trace_url is not None else None,
    )
    return workflow


def test_question_workflow_propagates_trace_url_from_factory() -> None:
    """The question workflow must call ``trace_url_factory(trace_id)`` and
    store the resulting URL on the execution so the API envelope can
    expose the canonical Langfuse URL without concatenating the
    ``/trace/<id>`` suffix by hand.
    """
    url = "https://langfuse.local/trace/trace-deadbeef"
    workflow = _stub_workflow_fixtures(trace_id="trace-deadbeef", trace_url=url)
    execution = asyncio.run(workflow.run(QueryInput("Pregunta", "es")))
    assert execution.trace_id == "trace-deadbeef"
    assert execution.trace_url == url


def test_question_workflow_leaves_trace_url_none_without_factory() -> None:
    """Without a ``trace_url_factory`` the workflow must NOT invent a URL
    and must leave the field ``None`` so the envelope falls back to the
    env-derived helper instead of emitting a broken link.
    """
    workflow = _stub_workflow_fixtures(trace_id="trace-feedface", trace_url=None)
    execution = asyncio.run(workflow.run(QueryInput("Pregunta", "es")))
    assert execution.trace_id == "trace-feedface"
    assert execution.trace_url is None
