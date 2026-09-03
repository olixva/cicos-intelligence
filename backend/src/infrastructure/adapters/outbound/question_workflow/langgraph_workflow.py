"""Bounded LangGraph orchestration for grounded document questions."""

import asyncio
import contextlib
import re
from collections.abc import Callable
from typing import NotRequired, Required, TypedDict, cast

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables import RunnableConfig
from langfuse import get_client
from langgraph.graph import END, START, StateGraph

from application.models.query import ContextEvidence, QueryExecution, QueryInput, QuestionAnswer
from application.ports.outbound.evidence_reader import EvidenceReader
from application.ports.outbound.language_model import LanguageModel
from application.ports.outbound.retriever import RetrievalMode, RetrievalRequest, Retriever
from application.services.question_answering import validate_grounded_answer


class QuestionWorkflowTimeoutError(TimeoutError):
    """The complete question graph exceeded its local execution budget."""


# Langfuse trace IDs are 32 lowercase hex characters; the SDK raises
# ``ValueError`` (after only logging a warning) when an invalid ID is
# passed to ``start_as_current_observation``. Guard the workflow so
# non-Langfuse traces (e.g. local tests with synthetic IDs) keep working.
_LANGFUSE_TRACE_ID_RE = re.compile(r"^[0-9a-f]{32}$")


class _QuestionState(TypedDict, total=False):
    query: Required[QueryInput]
    context: NotRequired[tuple[ContextEvidence, ...]]
    draft: NotRequired[QuestionAnswer]
    result: NotRequired[QuestionAnswer]


class _QuestionUpdate(TypedDict, total=False):
    context: tuple[ContextEvidence, ...]
    draft: QuestionAnswer
    result: QuestionAnswer


class LangGraphQuestionWorkflow:
    """Run retrieve, generate, and validate nodes with a typed internal state."""

    def __init__(
        self,
        *,
        retriever: Retriever,
        evidence_repository: EvidenceReader,
        language_model: LanguageModel,
        retrieval_mode: RetrievalMode = "hybrid",
        retrieval_limit: int = 8,
        timeout_seconds: float = 45.0,
        trace_id_factory: Callable[[], str | None] = lambda: None,
        callback_factory: Callable[[str], BaseCallbackHandler] | None = None,
        trace_url_factory: Callable[[str], str | None] | None = None,
    ) -> None:
        if type(retrieval_limit) is not int or retrieval_limit <= 0:
            raise ValueError("retrieval_limit must be a positive integer")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._retriever = retriever
        self._evidence_repository = evidence_repository
        self._language_model = language_model
        self._retrieval_mode: RetrievalMode = retrieval_mode
        self._retrieval_limit = retrieval_limit
        self._timeout_seconds = timeout_seconds
        self._trace_id_factory = trace_id_factory
        self._callback_factory = callback_factory
        self._trace_url_factory = trace_url_factory

        graph = StateGraph(_QuestionState)
        graph.add_node("retrieve", self._retrieve)  # pyright: ignore[reportUnknownMemberType]
        graph.add_node("generate", self._generate)  # pyright: ignore[reportUnknownMemberType]
        graph.add_node("validate", self._validate)  # pyright: ignore[reportUnknownMemberType]
        graph.add_edge(START, "retrieve")
        graph.add_edge("retrieve", "generate")
        graph.add_edge("generate", "validate")
        graph.add_edge("validate", END)
        self._graph = graph.compile()  # pyright: ignore[reportUnknownMemberType]

    async def run(self, query: QueryInput) -> QueryExecution:
        trace_id = self._trace_id_factory()
        config = RunnableConfig(recursion_limit=5)
        config["run_name"] = "allianz_question_answer"
        config["tags"] = ["allianz", "workflow:question_answer"]
        metadata: dict[str, str] = {"allianz_workflow": "question_answer"}
        if query.session_id:
            metadata.update(
                {"langfuse_session_id": query.session_id, "session_id": query.session_id}
            )
        config["metadata"] = metadata
        if trace_id is not None and self._callback_factory is not None:
            config["callbacks"] = [self._callback_factory(trace_id)]
        # Wrap the graph dispatch in a Langfuse span so the OpenTelemetry
        # context is attached to the asyncio task before any awaited
        # ``responses.parse`` call fires inside ``_generate``. The
        # ``langfuse.openai`` wrapper reads this OTEL context to nest its
        # ``GENERATION`` spans under the workflow's trace. Relying only on
        # ``CallbackHandler`` leaves orphan spans, because it dispatches
        # through ``run_in_executor`` and loses the ambient context.
        span_cm: contextlib.AbstractContextManager[object] = (
            get_client().start_as_current_observation(
                name="question_workflow",
                as_type="span",
                trace_context={"trace_id": trace_id},
                metadata={"session_id": query.session_id} if query.session_id else None,
            )
            if trace_id is not None and _LANGFUSE_TRACE_ID_RE.match(trace_id)
            else contextlib.nullcontext()
        )
        try:
            with span_cm:
                async with asyncio.timeout(self._timeout_seconds):
                    raw = await self._graph.ainvoke(  # pyright: ignore[reportUnknownMemberType]
                        _QuestionState(query=query), config=config
                    )
        except TimeoutError as error:
            raise QuestionWorkflowTimeoutError("question workflow timed out") from error
        state = cast(_QuestionState, raw)
        result = state.get("result")
        if result is None:
            raise RuntimeError("question workflow completed without a result")
        return QueryExecution(
            result=result,
            context=state.get("context", ()),
            trace_id=trace_id,
            trace_url=(
                self._trace_url_factory(trace_id)
                if trace_id is not None and self._trace_url_factory is not None
                else None
            ),
        )

    async def _retrieve(self, state: _QuestionState) -> _QuestionUpdate:
        query = state["query"]
        chunks = await self._retriever.retrieve(
            RetrievalRequest(query.text, self._retrieval_limit, self._retrieval_mode)
        )
        context: list[ContextEvidence] = []
        seen: set[tuple[tuple[str, ...], str]] = set()
        for chunk in chunks:
            identity = (chunk.evidence_ids, chunk.text)
            if identity in seen:
                continue
            seen.add(identity)
            context.append(
                ContextEvidence(
                    evidence_ids=chunk.evidence_ids,
                    text=chunk.text,
                    sources=tuple(
                        self._evidence_repository.get(evidence_id)
                        for evidence_id in chunk.evidence_ids
                    ),
                    delivery="text",
                )
            )
        return _QuestionUpdate(context=tuple(context))

    async def _generate(self, state: _QuestionState) -> _QuestionUpdate:
        context = state.get("context", ())
        if not context:
            return _QuestionUpdate(draft=QuestionAnswer("insufficient_evidence", ()))
        return _QuestionUpdate(draft=await self._language_model.generate(state["query"], context))

    def _validate(self, state: _QuestionState) -> _QuestionUpdate:
        draft = state.get("draft")
        if draft is None:
            raise RuntimeError("question workflow reached validation without a draft")
        return _QuestionUpdate(result=validate_grounded_answer(draft, state.get("context", ())))
