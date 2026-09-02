"""Bounded LangGraph orchestration for source-grounded claim applicability."""

import asyncio
import contextlib
import re
import uuid
from collections import defaultdict
from collections.abc import Callable
from typing import Literal, NotRequired, Required, TypedDict, cast

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables import RunnableConfig, RunnableLambda
from langfuse import get_client
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from application.models.claim import ClaimExecution, ExtractedClaimFacts, InterviewPlan
from application.models.query import ContextEvidence
from application.ports.outbound.claim_fact_extractor import ClaimFactExtractor
from application.ports.outbound.evidence_reader import EvidenceReader
from application.ports.outbound.retriever import RetrievalMode, RetrievalRequest, Retriever
from application.services.claim_analysis import build_applicability_analysis
from domain.models.claim import (
    ClaimContradiction,
    ClaimEvidenceBlock,
    ClaimFact,
    ClaimInput,
    MatrixCell,
)
from domain.models.decision import ClaimAnalysis
from domain.models.rule_evaluation import RuleEvaluation
from domain.rules.applicability import ApplicabilityFacts, assess_applicability
from domain.rules.cide_matrix import MatrixDecision, MatrixException, decide_from_daa_matrix
from domain.rules.ruleset import LoadedRule, evaluate_ruleset


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
    interview_plan: NotRequired[InterviewPlan]
    result: NotRequired[ClaimAnalysis]
    resumed: NotRequired[bool]


class _ClaimUpdate(TypedDict, total=False):
    extracted: ExtractedClaimFacts
    context: tuple[ContextEvidence, ...]
    analysis: ClaimAnalysis
    interview_plan: InterviewPlan
    result: ClaimAnalysis
    resumed: bool


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
        rules: tuple[LoadedRule, ...] = (),
        matrix_cells: dict[tuple[int, int], MatrixCell] | None = None,
        matrix_exceptions: tuple[MatrixException, ...] = (),
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
        self._rules = rules
        self._rules_by_id = {rule.rule_id: rule for rule in rules}
        self._matrix_cells = matrix_cells or {}
        self._matrix_exceptions = matrix_exceptions
        self._trace_id_factory = trace_id_factory
        self._callback_factory = callback_factory
        self._trace_url_factory = trace_url_factory
        graph = StateGraph(_ClaimState)
        graph.add_node("extract_facts", self._extract_facts)  # pyright: ignore[reportUnknownMemberType]
        graph.add_node("retrieve_criteria", self._retrieve_criteria)  # pyright: ignore[reportUnknownMemberType]
        graph.add_node("apply_rules", self._apply_rules)  # pyright: ignore[reportUnknownMemberType]
        graph.add_node("plan_interview", self._plan_interview)  # pyright: ignore[reportUnknownMemberType]
        graph.add_node("needs_information", self._needs_information)  # pyright: ignore[reportUnknownMemberType]
        graph.add_node("explain", self._explain)  # pyright: ignore[reportUnknownMemberType]
        graph.add_node("validate", self._validate)  # pyright: ignore[reportUnknownMemberType]
        graph.add_edge(START, "extract_facts")
        graph.add_edge("extract_facts", "retrieve_criteria")
        graph.add_edge("retrieve_criteria", "apply_rules")
        graph.add_edge("apply_rules", "plan_interview")
        graph.add_edge("plan_interview", "needs_information")
        graph.add_conditional_edges(
            "needs_information",
            RunnableLambda(
                self._route_after_information,
                name="route_after_information",
            ),
            {"extract_facts": "extract_facts", "explain": "explain"},
        )
        graph.add_edge("explain", "validate")
        graph.add_edge("validate", END)
        self._graph = graph.compile(checkpointer=MemorySaver())  # pyright: ignore[reportUnknownMemberType]

    async def run(self, claim: ClaimInput) -> ClaimExecution:
        trace_id = self._trace_id_factory()
        thread_id = claim.thread_id or str(uuid.uuid4())
        config = RunnableConfig(recursion_limit=12, configurable={"thread_id": thread_id})
        config["run_name"] = "allianz_claim_analysis"
        config["tags"] = ["allianz", "workflow:claim_analysis"]
        metadata: dict[str, str] = {"allianz_workflow": "claim_analysis"}
        if claim.session_id:
            metadata.update(
                {"langfuse_session_id": claim.session_id, "session_id": claim.session_id}
            )
        config["metadata"] = metadata
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
                metadata={"session_id": claim.session_id} if claim.session_id else None,
            )
            if trace_id is not None and _LANGFUSE_TRACE_ID_RE.match(trace_id)
            else contextlib.nullcontext()
        )
        try:
            with span_cm:
                async with asyncio.timeout(self._timeout_seconds):
                    raw = await self._graph.ainvoke(  # pyright: ignore[reportUnknownMemberType]
                        Command(resume={"clarifications": claim.clarifications})
                        if claim.resume
                        else _ClaimState(claim=claim),
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
            needs_input=bool(state.get("__interrupt__")),
            thread_id=thread_id,
            missing_information=result.missing_information if state.get("__interrupt__") else (),
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
            analysis = ClaimAnalysis(
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
            return _ClaimUpdate(analysis=analysis, result=analysis)
        assessment = assess_applicability(
            _applicability_facts(extracted.facts), evidence_ids=evidence_ids
        )
        raw_facts = {fact.name: fact.value for fact in extracted.facts if fact.value}
        # Cada regla del corpus firmado se ejecuta y se reporta, incluidas las
        # que no casan y las que no pueden comprobarse: la interfaz tiene que
        # poder enseñar qué se evaluó, no sólo el veredicto.
        evaluations = evaluate_ruleset(self._rules, raw_facts)
        matched_manoeuvre_rules = tuple(
            evaluation
            for evaluation in evaluations
            if evaluation.result == "matched" and self._kind_of(evaluation.rule_id) == "manoeuvre"
        )
        matrix_decision = decide_from_daa_matrix(
            self._matrix_cells,
            exceptions=self._matrix_exceptions,
            facts=raw_facts,
            prerequisites_confirmed=raw_facts.get("daa_section_12_only", "").strip().lower()
            == "true",
        )
        evaluations = _apply_matrix_evaluation(evaluations, matrix_decision)
        analysis = build_applicability_analysis(
            parties=extracted.party_ids,
            facts=extracted.facts,
            assessment=assessment,
            matched_manoeuvre_rules=matched_manoeuvre_rules,
            manoeuvre_convention=(
                self._convention_of(matched_manoeuvre_rules[0].rule_id)
                if len(matched_manoeuvre_rules) == 1
                else None
            ),
            # Una D.A.A. declarada y una maniobra reconocida no deberían coexistir
            # en el mismo relato; si por lo que sea lo hicieran, se prioriza la
            # norma subsidiaria ya resuelta y la matriz no se consulta, en vez de
            # elegir entre dos caminos que discrepan.
            matrix_decision=matrix_decision if len(matched_manoeuvre_rules) != 1 else None,
            matrix_convention=self._convention_of("cide-matrix-lookup"),
        )
        blocks = analysis.blocks or _rule_blocks(evaluations)
        analysis = ClaimAnalysis(
            analysis.applicability,
            analysis.convention,
            analysis.decision,
            analysis.party_ids,
            analysis.facts,
            _contradictions(extracted.facts),
            analysis.conditions,
            analysis.missing_information,
            blocks,
            rules_evaluated=evaluations,
        )
        return _ClaimUpdate(analysis=analysis, result=analysis)

    def _plan_interview(self, state: _ClaimState) -> _ClaimUpdate:
        """Apply the LLM interview plan as an explicit LangGraph transition.

        The extractor decides the plan in the same call that reads the facts,
        before ``apply_rules`` has run: it cannot know that the deterministic
        gate already excluded the Convenio (vehicle count, chain collision, an
        identified third vehicle). Once ``analysis.applicability`` is
        ``"not_applicable"`` there is nothing left to ask — planning a
        follow-up question here produced exactly the invariant violation this
        guard exists to prevent.
        """
        extracted = state.get("extracted")
        analysis = state.get("analysis")
        if extracted is None or analysis is None:
            raise RuntimeError(
                "claim workflow reached interview planning without facts and analysis"
            )
        if analysis.applicability == "not_applicable":
            return _ClaimUpdate(
                interview_plan=InterviewPlan("coverage_gap", terminal_reason="not_applicable"),
                analysis=analysis,
                result=analysis,
            )
        plan = extracted.interview_plan
        if plan.status == "ask":
            prompts = tuple(question.prompt for question in plan.questions)
            analysis = ClaimAnalysis(
                analysis.applicability,
                analysis.convention,
                "conditional",
                analysis.party_ids,
                analysis.facts,
                analysis.contradictions,
                prompts,
                prompts,
                analysis.blocks,
                rules_evaluated=analysis.rules_evaluated,
            )
        elif plan.status in ("inconsistent", "coverage_gap"):
            reason = plan.terminal_reason
            if reason is None:
                raise RuntimeError("terminal interview plan has no reason")
            evidence_ids = tuple(
                dict.fromkeys(
                    item for group in state.get("context", ()) for item in group.evidence_ids
                )
            )
            analysis = ClaimAnalysis(
                analysis.applicability,
                analysis.convention,
                "undetermined",
                analysis.party_ids,
                analysis.facts,
                analysis.contradictions,
                (),
                (),
                (ClaimEvidenceBlock(reason, evidence_ids),),
                rules_evaluated=analysis.rules_evaluated,
            )
        return _ClaimUpdate(interview_plan=plan, analysis=analysis, result=analysis)

    @staticmethod
    def _route_after_information(
        state: _ClaimState,
    ) -> Literal["extract_facts", "explain"]:
        return "extract_facts" if state.get("resumed") else "explain"

    def _kind_of(self, rule_id: str) -> str | None:
        rule = self._rules_by_id.get(rule_id)
        return rule.kind if rule is not None else None

    def _convention_of(self, rule_id: str) -> Literal["CIDE", "ASCIDE"] | None:
        """Read the convention from the signed artifact; never infer it from ``kind``."""
        rule = self._rules_by_id.get(rule_id)
        return rule.convention if rule is not None else None

    def _explain(self, state: _ClaimState) -> _ClaimUpdate:
        """Keep deterministic result; this node is the future explanation extension seam."""
        analysis = state.get("analysis")
        if analysis is None:
            raise RuntimeError("claim workflow reached explanation without analysis")
        return _ClaimUpdate(result=analysis)

    def _needs_information(self, state: _ClaimState) -> _ClaimUpdate:
        analysis = state.get("analysis")
        if analysis is None:
            raise RuntimeError("claim workflow reached information gate without analysis")
        if not analysis.missing_information:
            # ``resumed`` is a routing marker for the current interruption
            # only. Clear it once the resumed extraction is complete, or the
            # conditional edge would restart extraction indefinitely.
            return _ClaimUpdate(result=analysis, resumed=False)
        response = interrupt({"missing_information": analysis.missing_information})
        response_dict = cast(dict[str, object], response) if isinstance(response, dict) else {}
        raw_clarifications = response_dict.get("clarifications", ())
        clarifications: tuple[str, ...] = ()
        if isinstance(raw_clarifications, (list, tuple)):
            clarification_values = cast(list[object] | tuple[object, ...], raw_clarifications)
            clarifications = tuple(item for item in clarification_values if isinstance(item, str))
        claim = state["claim"]
        # LangGraph re-enters this node on every resume. Keep the answers
        # already supplied in the checkpoint and append the new batch; the
        # frontend intentionally sends only the fields answered in that step.
        merged_clarifications: tuple[str, ...] = tuple(
            dict.fromkeys((*claim.clarifications, *clarifications))
        )
        resumed_claim = ClaimInput(
            claim.text,
            claim.language,
            merged_clarifications,
            session_id=claim.session_id,
            thread_id=claim.thread_id,
            resume=True,
        )
        return {"claim": resumed_claim, "resumed": True, "result": analysis}  # type: ignore[return-value]

    def _validate(self, state: _ClaimState) -> _ClaimUpdate:
        analysis = state.get("result")
        if analysis is None:
            raise RuntimeError("claim workflow reached validation without a result")
        # The frozen domain value has already validated its invariants on construction.
        return _ClaimUpdate(result=analysis)


def _applicability_facts(facts: tuple[ClaimFact, ...]) -> ApplicabilityFacts:
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


def _contradictions(facts: tuple[ClaimFact, ...]) -> tuple[ClaimContradiction, ...]:
    by_name: dict[str, list[ClaimFact]] = defaultdict(list)
    for fact in facts:
        if fact.value is not None:
            by_name[fact.name].append(fact)
    return tuple(
        ClaimContradiction(name, tuple(statements))
        for name, statements in by_name.items()
        if len({statement.value for statement in statements}) > 1 and len(statements) > 1
    )


def _apply_matrix_evaluation(
    evaluations: tuple[RuleEvaluation, ...], decision: MatrixDecision
) -> tuple[RuleEvaluation, ...]:
    """Replace the generic ``cide-matrix-lookup`` placeholder with what the table said.

    ``evaluate_ruleset`` always reports this rule as ``insufficient_data``: it is
    a lookup, not a boolean predicate, so it has no ``applies_when`` to evaluate.
    When the caller declared a D.A.A. pair, this substitutes the real outcome so
    the audit trail shows what the table actually decided, not a placeholder.
    """
    if decision.status == "undetermined":
        return evaluations
    rationale = _matrix_rationale(decision)
    replaced = tuple(
        RuleEvaluation(
            rule_id=evaluation.rule_id,
            inputs=evaluation.inputs,
            result="matched",
            evidence_ids=decision.evidence_ids,
            rationale=rationale,
        )
        if evaluation.rule_id == "cide-matrix-lookup"
        else evaluation
        for evaluation in evaluations
    )
    return replaced


def _matrix_rationale(decision: MatrixDecision) -> str:
    if decision.status == "attributes":
        return f"Tabla de culpabilidad CIDE: atribuye la responsabilidad a {decision.liable_party}."
    if decision.status == "no_attribution":
        return "Tabla de culpabilidad CIDE: la celda declarada no atribuye responsabilidad."
    assert decision.exception_text is not None
    if decision.status == "needs_exception_fact":
        return (
            "Tabla de culpabilidad CIDE: pendiente de la observación — "
            f"{decision.exception_text}"
        )
    return f"Tabla de culpabilidad CIDE: la observación se cumple — {decision.exception_text}"


def _rule_blocks(evaluations: tuple[RuleEvaluation, ...]) -> tuple[ClaimEvidenceBlock, ...]:
    """Turn the rules that actually matched into cited explanation blocks.

    Only matched rules become text: a rule that did not hold, or that could
    not be checked, is reported in ``rules_evaluated`` but never narrated as
    if it had driven the outcome.
    """

    return tuple(
        ClaimEvidenceBlock(evaluation.rationale, evaluation.evidence_ids)
        for evaluation in evaluations
        if evaluation.result == "matched" and evaluation.evidence_ids
    )
