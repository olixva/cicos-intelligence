"""Bounded LangGraph orchestration for source-grounded claim applicability."""

import asyncio
import contextlib
import re
from collections import defaultdict
from collections.abc import Callable
from typing import NotRequired, Required, TypedDict, cast

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables import RunnableConfig
from langfuse import get_client
from langgraph.graph import END, START, StateGraph

from application.models.claim import ClaimExecution, ExtractedClaimFacts
from application.models.query import ContextEvidence
from application.ports.outbound.claim_fact_extractor import ClaimFactExtractor
from application.ports.outbound.evidence_reader import EvidenceReader
from application.ports.outbound.retriever import RetrievalMode, RetrievalRequest, Retriever
from application.services.claim_analysis import build_applicability_analysis
from domain.models.claim import ClaimContradiction, ClaimInput
from domain.models.decision import ClaimAnalysis
from domain.rules.applicability import ApplicabilityFacts, assess_applicability


class ClaimWorkflowTimeoutError(TimeoutError):
    """The claim graph exceeded its local execution budget."""


# Langfuse trace IDs are 32 lowercase hex characters; the SDK raises
# ``ValueError`` (after only logging a warning) when an invalid ID is
# passed to ``start_as_current_observation``. Guard the workflow so
# non-Langfuse traces (e.g. local tests with synthetic IDs) keep working.
_LANGFUSE_TRACE_ID_RE = re.compile(r"^[0-9a-f]{32}$")


class _ClaimState(TypedDict, total=False):
    claim: Required[ClaimInput]
    extracted: NotRequired[ExtractedClaimFacts]
    context: NotRequired[tuple[ContextEvidence, ...]]
    analysis: NotRequired[ClaimAnalysis]
    result: NotRequired[ClaimAnalysis]


class _ClaimUpdate(TypedDict, total=False):
    extracted: ExtractedClaimFacts
    context: tuple[ContextEvidence, ...]
    analysis: ClaimAnalysis
    result: ClaimAnalysis


class LangGraphClaimWorkflow:
    """Extract facts, retrieve criteria, apply deterministic guards, and validate."""

    def __init__(
        self,
        *,
        fact_extractor: ClaimFactExtractor,
        retriever: Retriever,
        evidence_repository: EvidenceReader,
        retrieval_mode: RetrievalMode = "hybrid",
        retrieval_limit: int = 6,
        timeout_seconds: float = 30.0,
        trace_id_factory: Callable[[], str | None] = lambda: None,
        trace_url_factory: Callable[[str], str | None] | None = None,
        callback_factory: Callable[[str], BaseCallbackHandler] | None = None,
    ) -> None:
        if type(retrieval_limit) is not int or retrieval_limit <= 0:
            raise ValueError("retrieval_limit must be a positive integer")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._fact_extractor = fact_extractor
        self._retriever = retriever
        self._evidence_repository = evidence_repository
        self._retrieval_mode: RetrievalMode = retrieval_mode
        self._retrieval_limit = retrieval_limit
        self._timeout_seconds = timeout_seconds
        self._trace_id_factory = trace_id_factory
        self._callback_factory = callback_factory
        self._trace_url_factory = trace_url_factory
        graph = StateGraph(_ClaimState)
        graph.add_node("extract_facts", self._extract_facts)  # pyright: ignore[reportUnknownMemberType]
        graph.add_node("retrieve_criteria", self._retrieve_criteria)  # pyright: ignore[reportUnknownMemberType]
        graph.add_node("apply_rules", self._apply_rules)  # pyright: ignore[reportUnknownMemberType]
        graph.add_node("explain", self._explain)  # pyright: ignore[reportUnknownMemberType]
        graph.add_node("validate", self._validate)  # pyright: ignore[reportUnknownMemberType]
        graph.add_edge(START, "extract_facts")
        graph.add_edge("extract_facts", "retrieve_criteria")
        graph.add_edge("retrieve_criteria", "apply_rules")
        graph.add_edge("apply_rules", "explain")
        graph.add_edge("explain", "validate")
        graph.add_edge("validate", END)
        self._graph = graph.compile()  # pyright: ignore[reportUnknownMemberType]

    async def run(self, claim: ClaimInput) -> ClaimExecution:
        trace_id = self._trace_id_factory()
        config = RunnableConfig(recursion_limit=8)
        if trace_id is not None and self._callback_factory is not None:
            config["callbacks"] = [self._callback_factory(trace_id)]  # type: ignore[arg-type]
        # Wrap the graph dispatch in a Langfuse span so the OpenTelemetry
        # context is attached to the asyncio task before any awaited
        # ``responses.parse`` call fires inside ``_extract_facts``. The
        # ``langfuse.openai`` wrapper reads this OTEL context to nest its
        # ``GENERATION`` spans under the workflow's trace (Oracle G4
        # residual finding: orphan spans when only ``CallbackHandler`` is
        # used because it dispatches via ``run_in_executor``).
        span_cm: contextlib.AbstractContextManager[object] = (
            get_client().start_as_current_observation(
                name="claim_workflow",
                as_type="span",
                trace_context={"trace_id": trace_id},
            )
            if trace_id is not None and _LANGFUSE_TRACE_ID_RE.match(trace_id)
            else contextlib.nullcontext()
        )
        try:
            with span_cm:
                async with asyncio.timeout(self._timeout_seconds):
                    raw = await self._graph.ainvoke(  # pyright: ignore[reportUnknownMemberType]
                        _ClaimState(claim=claim),
                        config=config,  # type: ignore[arg-type]
                    )
        except TimeoutError as error:
            raise ClaimWorkflowTimeoutError("claim workflow timed out") from error
        state = cast(_ClaimState, raw)
        result = state.get("result")
        if result is None:
            raise RuntimeError("claim workflow completed without a result")
        return ClaimExecution(
            result,
            state.get("context", ()),
            trace_id,
            trace_url=(
                self._trace_url_factory(trace_id)
                if trace_id is not None and self._trace_url_factory is not None
                else None
            ),
        )

    async def _extract_facts(self, state: _ClaimState) -> _ClaimUpdate:
        return _ClaimUpdate(extracted=await self._fact_extractor.extract(state["claim"]))

    async def _retrieve_criteria(self, state: _ClaimState) -> _ClaimUpdate:
        chunks = await self._retriever.retrieve(
            RetrievalRequest(state["claim"].text, self._retrieval_limit, self._retrieval_mode)
        )
        context: list[ContextEvidence] = []
        seen: set[tuple[tuple[str, ...], str]] = set()
        for chunk in chunks:
            identity = (chunk.evidence_ids, chunk.text)
            if identity not in seen:
                seen.add(identity)
                context.append(
                    ContextEvidence(
                        chunk.evidence_ids,
                        chunk.text,
                        tuple(self._evidence_repository.get(item) for item in chunk.evidence_ids),
                    )
                )
        return _ClaimUpdate(context=tuple(context))

    def _apply_rules(self, state: _ClaimState) -> _ClaimUpdate:
        extracted = state.get("extracted")
        if extracted is None:
            raise RuntimeError("claim workflow reached rules without extracted facts")
        context = state.get("context", ())
        evidence_ids = tuple(
            dict.fromkeys(item for group in context for item in group.evidence_ids)
        )
        if not evidence_ids:
            return _ClaimUpdate(
                analysis=ClaimAnalysis(
                    "undetermined",
                    None,
                    "conditional",
                    extracted.party_ids,
                    extracted.facts,
                    _contradictions(extracted.facts),
                    ("Recuperar el criterio del manual antes de aplicar el Convenio.",),
                    ("No se recuperó evidencia documental aplicable.",),
                    (),
                )
            )
        assessment = assess_applicability(
            _applicability_facts(extracted.facts), evidence_ids=evidence_ids
        )
        analysis = build_applicability_analysis(
            parties=extracted.party_ids, facts=extracted.facts, assessment=assessment
        )
        return _ClaimUpdate(
            analysis=ClaimAnalysis(
                analysis.applicability,
                analysis.convention,
                analysis.decision,
                analysis.party_ids,
                analysis.facts,
                _contradictions(extracted.facts),
                analysis.conditions,
                analysis.missing_information,
                analysis.blocks,
            )
        )

    def _explain(self, state: _ClaimState) -> _ClaimUpdate:
        """Keep deterministic result; this node is the future explanation extension seam."""
        analysis = state.get("analysis")
        if analysis is None:
            raise RuntimeError("claim workflow reached explanation without analysis")
        return _ClaimUpdate(result=analysis)

    def _validate(self, state: _ClaimState) -> _ClaimUpdate:
        analysis = state.get("result")
        if analysis is None:
            raise RuntimeError("claim workflow reached validation without a result")
        # The frozen domain value has already validated its invariants on construction.
        return _ClaimUpdate(result=analysis)


def _applicability_facts(facts: tuple) -> ApplicabilityFacts:
    values = {fact.name: fact.value for fact in facts if fact.value is not None}
    return ApplicabilityFacts(
        vehicle_count=_integer(values.get("vehicle_count")),
        direct_collision=_boolean(values.get("direct_collision")),
        third_vehicle_identified=_boolean(values.get("third_vehicle_identified")),
        chain_collision=_boolean(values.get("chain_collision")),
    )


def _integer(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _boolean(value: str | None) -> bool | None:
    if value is None:
        return None
    return {"true": True, "false": False}.get(value.strip().lower())


def _contradictions(facts: tuple) -> tuple[ClaimContradiction, ...]:
    by_name: dict[str, list] = defaultdict(list)
    for fact in facts:
        if fact.value is not None:
            by_name[fact.name].append(fact)
    return tuple(
        ClaimContradiction(name, tuple(statements))
        for name, statements in by_name.items()
        if len({statement.value for statement in statements}) > 1 and len(statements) > 1
    )
