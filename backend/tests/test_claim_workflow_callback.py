"""Verify the Langfuse ``CallbackHandler`` is wired into the claim workflow.

Oracle G4 finding #2: ``LangGraphClaimWorkflow`` did not accept a
``callback_factory``, so claim traces returned 0 observations in
Langfuse. After the fix the constructor accepts the same factory the
question workflow already takes; passing it must make the graph dispatch
the returned handler through ``RunnableConfig.callbacks`` so the
Langfuse ``CallbackHandler`` attaches its spans to the running trace.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Protocol

from application.models.claim import ExtractedClaimFacts
from application.models.retrieval import Chunk
from application.ports.outbound.claim_fact_extractor import ClaimFactExtractor
from application.ports.outbound.evidence_reader import EvidenceReader
from application.ports.outbound.retriever import RetrievalRequest, Retriever
from domain.models.claim import ClaimFact, ClaimInput
from domain.models.evidence import PageEvidence


@dataclass
class _Extractor(ClaimFactExtractor):
    result: ExtractedClaimFacts

    async def extract(self, claim: ClaimInput) -> ExtractedClaimFacts:
        return self.result


class _Retriever(Retriever):
    async def retrieve(self, request: RetrievalRequest) -> tuple[Chunk, ...]:
        return (Chunk("criteria", "El Convenio exige dos vehículos.", ("manual:page:56",)),)


@dataclass
class _Evidence(EvidenceReader):
    page: PageEvidence

    def get(self, evidence_id: str) -> PageEvidence:
        return self._pages[evidence_id]

    def __post_init__(self) -> None:
        self._pages = {self.page.evidence_id: self.page}


class _CallbackLike(Protocol):
    """Minimum interface the LangChain ``RunnableConfig`` needs from a handler."""

    trace_id: str


class _RecordingCallbackHandler(_CallbackLike):
    """Minimal stand-in for ``langchain_core.callbacks.BaseCallbackHandler``.

    The production ``CallbackHandler`` from ``langfuse.langchain`` is
    non-trivial (it sends HTTP requests to Langfuse) so the wiring test
    substitutes a deterministic handler whose identity we can assert on.
    """

    instances: list[tuple[str, _RecordingCallbackHandler]] = []

    def __init__(self, trace_id: str) -> None:
        self.trace_id = trace_id
        _RecordingCallbackHandler.instances.append((trace_id, self))


def _extract_callbacks(config: Any) -> Any:
    """Return the callbacks list from a ``RunnableConfig`` regardless of shape.

    ``RunnableConfig`` accepts a dict-like or object-like form; both must
    yield the same callbacks list so the wiring is asserted uniformly.
    """

    callbacks = getattr(config, "callbacks", None)
    if callbacks is None and hasattr(config, "get"):
        callbacks = config.get("callbacks")
    return callbacks


def test_claim_workflow_passes_callback_factory_to_graph_config() -> None:
    """A provided ``callback_factory`` is invoked with the trace id and the
    returned handler is forwarded into the LangGraph ``RunnableConfig``.

    We intercept the compiled graph so we can capture the callback that
    would have been passed to ``ainvoke`` without depending on LangGraph
    internals — we only verify the wiring is structurally correct.
    """

    from infrastructure.adapters.outbound.claim_workflow.langgraph_workflow import (
        LangGraphClaimWorkflow,
    )

    captured: dict[str, Any] = {}

    class _StubGraph:
        async def ainvoke(self, state: Any, config: Any | None = None) -> Any:
            captured["config"] = config
            return {
                "result": _Extractor(ExtractedClaimFacts(("A", "B"), ())).result,
                "context": (),
                "claim": state["claim"],
            }

    def factory(trace_id: str) -> _CallbackLike:
        return _RecordingCallbackHandler(trace_id)

    workflow = LangGraphClaimWorkflow(
        fact_extractor=_Extractor(ExtractedClaimFacts(("A", "B"), ())),
        retriever=_Retriever(),
        evidence_repository=_Evidence(
            PageEvidence("manual:page:56", "a" * 64, 56, "texto", None, None, ())
        ),
        trace_id_factory=lambda: "trace-claim-42",
        callback_factory=factory,  # type: ignore[arg-type]
    )
    workflow._graph = _StubGraph()  # type: ignore[assignment]

    asyncio.run(workflow.run(ClaimInput("Hubo un accidente entre A y B.")))

    config = captured["config"]
    assert config is not None
    callbacks = _extract_callbacks(config)
    assert callbacks is not None, "config must carry a callbacks list"
    assert len(callbacks) == 1
    handler = callbacks[0]
    assert isinstance(handler, _RecordingCallbackHandler)
    assert handler.trace_id == "trace-claim-42"


def test_claim_workflow_without_callback_factory_omits_callbacks() -> None:
    """When no factory is supplied the graph still runs and produces a result."""

    from infrastructure.adapters.outbound.claim_workflow.langgraph_workflow import (
        LangGraphClaimWorkflow,
    )

    captured: dict[str, Any] = {}

    class _StubGraph:
        async def ainvoke(self, state: Any, config: Any | None = None) -> Any:
            captured["config"] = config
            return {"result": None, "context": (), "claim": state["claim"]}

    workflow = LangGraphClaimWorkflow(
        fact_extractor=_Extractor(ExtractedClaimFacts(("A", "B"), ())),
        retriever=_Retriever(),
        evidence_repository=_Evidence(
            PageEvidence("manual:page:56", "a" * 64, 56, "texto", None, None, ())
        ),
    )
    workflow._graph = _StubGraph()  # type: ignore[assignment]

    try:
        asyncio.run(workflow.run(ClaimInput("...")))
    except RuntimeError:
        # ``run`` raises if the graph returns no result; that's fine here
        # because we only assert the config did not carry a callback.
        pass

    config = captured.get("config")
    assert config is not None
    callbacks = _extract_callbacks(config)
    assert callbacks in (None, ()), "no callback factory must mean no callbacks wired"


def test_claim_workflow_skips_callback_when_trace_id_is_none() -> None:
    """A ``None`` trace id must not invoke the factory (mirrors the question workflow)."""

    from infrastructure.adapters.outbound.claim_workflow.langgraph_workflow import (
        LangGraphClaimWorkflow,
    )

    captured: dict[str, Any] = {}
    factory_calls: list[str] = []

    class _StubGraph:
        async def ainvoke(self, state: Any, config: Any | None = None) -> Any:
            captured["config"] = config
            return {"result": None, "context": (), "claim": state["claim"]}

    def factory(trace_id: str) -> _CallbackLike:
        factory_calls.append(trace_id)
        return _RecordingCallbackHandler(trace_id)

    workflow = LangGraphClaimWorkflow(
        fact_extractor=_Extractor(ExtractedClaimFacts(("A", "B"), ())),
        retriever=_Retriever(),
        evidence_repository=_Evidence(
            PageEvidence("manual:page:56", "a" * 64, 56, "texto", None, None, ())
        ),
        trace_id_factory=lambda: None,
        callback_factory=factory,  # type: ignore[arg-type]
    )
    workflow._graph = _StubGraph()  # type: ignore[assignment]

    try:
        asyncio.run(workflow.run(ClaimInput("...")))
    except RuntimeError:
        pass

    assert factory_calls == [], "factory must not be called when trace_id is None"
    config = captured.get("config")
    callbacks = _extract_callbacks(config)
    assert callbacks in (None, ())


def test_claim_workflow_constructor_accepts_callback_factory_kwarg() -> None:
    """The new constructor kwarg must compile without raising."""

    from infrastructure.adapters.outbound.claim_workflow.langgraph_workflow import (
        LangGraphClaimWorkflow,
    )

    workflow = LangGraphClaimWorkflow(
        fact_extractor=_Extractor(ExtractedClaimFacts(("A", "B"), ())),
        retriever=_Retriever(),
        evidence_repository=_Evidence(
            PageEvidence("manual:page:56", "a" * 64, 56, "texto", None, None, ())
        ),
        callback_factory=None,
    )
    assert workflow._callback_factory is None  # type: ignore[attr-defined]


# Keep ``ClaimFact`` import in case future tests in this file need it; the
# dataclass-based test doubles above are the contract surface today.
_ = ClaimFact
