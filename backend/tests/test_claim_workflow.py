"""Grafo de siniestros: aplicacion de reglas, tabla CIDE, entrevista y trazas."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from application.models.claim import (
    ClaimExecution,
    ExtractedClaimFacts,
    InterviewPlan,
    InterviewQuestion,
)
from application.models.retrieval import Chunk
from application.ports.outbound.claim_fact_extractor import ClaimFactExtractor
from application.ports.outbound.evidence_reader import EvidenceReader
from application.ports.outbound.retriever import RetrievalRequest, Retriever
from domain.models.claim import ClaimFact, ClaimInput, MatrixCell
from domain.models.evidence import PageEvidence
from domain.rules.cide_matrix import MatrixException
from domain.rules.ruleset import LoadedRule
from infrastructure.adapters.outbound.claim_workflow.langgraph_workflow import (
    LangGraphClaimWorkflow,
)
from infrastructure.config.rules_artifacts import load_rules_artifacts

# --------------------------------------------------------------------------
# LangGraph claim workflow keeps facts attributable and gates outcomes by evidence.
# --------------------------------------------------------------------------


@dataclass
class _Extractor(ClaimFactExtractor):
    result: ExtractedClaimFacts

    async def extract(self, claim: ClaimInput) -> ExtractedClaimFacts:
        return self.result


@dataclass
class _Retriever(Retriever):
    """Devuelve un único criterio recuperado, con el texto que pida el caso."""

    text: str = "El Convenio exige dos vehículos."

    async def retrieve(self, request: RetrievalRequest) -> tuple[Chunk, ...]:
        assert request.limit == 6
        return (Chunk("criteria", self.text, ("manual:page:56",)),)


@dataclass
class _Evidence(EvidenceReader):
    page: PageEvidence

    def get(self, evidence_id: str) -> PageEvidence:
        assert evidence_id == self.page.evidence_id
        return self.page


class _InterviewExtractor(ClaimFactExtractor):
    async def extract(self, claim: ClaimInput) -> ExtractedClaimFacts:
        if not claim.clarifications:
            return ExtractedClaimFacts(
                ("A", "B"),
                (ClaimFact("vehicle_count", "2", None, "dos vehículos"),),
                InterviewPlan(
                    "ask",
                    (
                        InterviewQuestion(
                            id="direct_collision",
                            prompt="¿Hubo colisión directa?",
                            reason="Es necesaria para comprobar el ámbito.",
                            answer_kind="boolean",
                        ),
                    ),
                ),
            )
        return ExtractedClaimFacts(
            ("A", "B"),
            (
                ClaimFact("vehicle_count", "2", None, "dos vehículos"),
                ClaimFact("direct_collision", "true", None, "sí, choque directo"),
                ClaimFact("maneuver_a", "detenido", "A", "A estaba detenido"),
            ),
            InterviewPlan("ready"),
        )


def test_claim_graph_preserves_conflicting_attributions_and_gates_inapplicable_case() -> None:
    from infrastructure.adapters.outbound.claim_workflow.langgraph_workflow import (
        LangGraphClaimWorkflow,
    )

    facts = (
        ClaimFact("vehicle_count", "3", None, "intervienen tres vehículos"),
        ClaimFact("traffic_light", "verde", "A", "A dice verde"),
        ClaimFact("traffic_light", "rojo", "B", "B dice rojo"),
    )
    workflow = LangGraphClaimWorkflow(
        fact_extractor=_Extractor(ExtractedClaimFacts(("A", "B"), facts)),
        retriever=_Retriever(),
        evidence_repository=_Evidence(
            PageEvidence("manual:page:56", "a" * 64, 56, "texto", None, None, ())
        ),
    )

    execution: ClaimExecution = asyncio.run(
        workflow.run(ClaimInput("A dice verde; B dice rojo; intervienen tres vehículos."))
    )

    assert execution.result.applicability == "not_applicable"
    assert execution.result.decision == "not_assessed"
    assert execution.result.contradictions[0].fact_name == "traffic_light"
    contradiction_values = {fact.value for fact in execution.result.contradictions[0].statements}
    assert contradiction_values == {"verde", "rojo"}
    assert execution.result.blocks[0].evidence_ids == ("manual:page:56",)
    assert execution.context[0].evidence_ids == ("manual:page:56",)


def test_claim_graph_ignores_the_interview_plan_once_rules_exclude_the_convention() -> None:
    """Regresión real: un siniestro de cinco turismos en cadena preguntaba por
    el orden de los impactos aunque `assess_applicability` ya había descartado
    el Convenio determinísticamente. El LLM decide su plan de entrevista en la
    misma llamada que extrae los hechos, antes de que las reglas se apliquen,
    así que no puede saber que el caso ya está cerrado — el grafo tiene que
    descartar ese plan cuando `apply_rules` ya dijo `not_applicable`."""
    from application.models.claim import InterviewPlan, InterviewQuestion
    from infrastructure.adapters.outbound.claim_workflow.langgraph_workflow import (
        LangGraphClaimWorkflow,
    )

    facts = (
        ClaimFact("vehicle_count", "5", None, "intervienen cinco turismos"),
        ClaimFact("chain_collision", "true", None, "colisión en cadena"),
    )
    plan = InterviewPlan(
        "ask",
        (
            InterviewQuestion(
                id="impact_order",
                prompt="¿Cuál fue el primer impacto?",
                reason="Necesario para reconstruir la secuencia.",
                answer_kind="text",
            ),
        ),
    )
    workflow = LangGraphClaimWorkflow(
        fact_extractor=_Extractor(ExtractedClaimFacts(("A", "B", "C", "D", "E"), facts, plan)),
        retriever=_Retriever(),
        evidence_repository=_Evidence(
            PageEvidence("manual:page:56", "a" * 64, 56, "texto", None, None, ())
        ),
    )

    execution: ClaimExecution = asyncio.run(
        workflow.run(ClaimInput("Colisión en cadena de cinco turismos."))
    )

    assert execution.needs_input is False
    assert execution.result.applicability == "not_applicable"
    assert execution.result.decision == "not_assessed"


def test_claim_graph_requests_missing_prerequisites_without_inventing_a_conclusion() -> None:
    from infrastructure.adapters.outbound.claim_workflow.langgraph_workflow import (
        LangGraphClaimWorkflow,
    )

    workflow = LangGraphClaimWorkflow(
        fact_extractor=_Extractor(ExtractedClaimFacts(("A", "B"), ())),
        retriever=_Retriever(),
        evidence_repository=_Evidence(
            PageEvidence("manual:page:56", "a" * 64, 56, "texto", None, None, ())
        ),
    )

    execution = asyncio.run(workflow.run(ClaimInput("Hubo un accidente entre A y B.")))

    assert execution.needs_input is True
    assert execution.thread_id
    assert execution.missing_information
    assert execution.result.applicability == "undetermined"
    assert execution.result.decision == "conditional"
    assert "cuántos vehículos" in execution.result.conditions[0]


def test_claim_graph_uses_the_llm_interview_question_before_emitting_a_result() -> None:
    from infrastructure.adapters.outbound.claim_workflow.langgraph_workflow import (
        LangGraphClaimWorkflow,
    )

    question = InterviewQuestion(
        id="vehicle_a_signal",
        prompt="¿Qué color tenía el semáforo del vehículo A?",
        reason="La señal puede cambiar la prioridad.",
        answer_kind="choice",
        options=("Rojo", "Ámbar", "Verde", "No se sabe"),
    )
    workflow = LangGraphClaimWorkflow(
        fact_extractor=_Extractor(
            ExtractedClaimFacts(
                ("A", "B"),
                (ClaimFact("vehicle_count", "2", None, "dos vehículos"),),
                InterviewPlan("ask", (question,)),
            )
        ),
        retriever=_Retriever(),
        evidence_repository=_Evidence(
            PageEvidence("manual:page:56", "a" * 64, 56, "texto", None, None, ())
        ),
    )

    execution = asyncio.run(workflow.run(ClaimInput("Dos vehículos chocaron en un cruce.")))

    assert execution.needs_input is True
    assert execution.missing_information == (question.prompt,)


def test_claim_graph_exposes_a_dedicated_interview_planning_node() -> None:
    from infrastructure.adapters.outbound.claim_workflow.langgraph_workflow import (
        LangGraphClaimWorkflow,
    )

    workflow = LangGraphClaimWorkflow(
        fact_extractor=_Extractor(ExtractedClaimFacts(("A", "B"), ())),
        retriever=_Retriever(),
        evidence_repository=_Evidence(
            PageEvidence("manual:page:56", "a" * 64, 56, "texto", None, None, ())
        ),
    )

    assert "plan_interview" in workflow._graph.get_graph().nodes  # pyright: ignore[reportPrivateUsage]


def test_claim_graph_resumes_after_an_answer_without_repeating_the_question() -> None:
    from infrastructure.adapters.outbound.claim_workflow.langgraph_workflow import (
        LangGraphClaimWorkflow,
    )

    workflow = LangGraphClaimWorkflow(
        fact_extractor=_InterviewExtractor(),
        retriever=_Retriever(),
        evidence_repository=_Evidence(
            PageEvidence("manual:page:56", "a" * 64, 56, "texto", None, None, ())
        ),
    )
    first = asyncio.run(workflow.run(ClaimInput("Dos vehículos tuvieron un accidente.")))
    resumed = asyncio.run(
        workflow.run(
            ClaimInput(
                "Dos vehículos tuvieron un accidente.",
                clarifications=("Sí, hubo colisión directa.",),
                thread_id=first.thread_id,
                resume=True,
            )
        )
    )

    assert first.needs_input is True
    assert resumed.needs_input is False


def test_claim_graph_surfaces_a_coverage_gap_without_asking_again() -> None:
    from infrastructure.adapters.outbound.claim_workflow.langgraph_workflow import (
        LangGraphClaimWorkflow,
    )

    workflow = LangGraphClaimWorkflow(
        fact_extractor=_Extractor(
            ExtractedClaimFacts(
                ("A", "B"),
                (
                    ClaimFact("vehicle_count", "2", None, "dos vehículos"),
                    ClaimFact("direct_collision", "true", None, "choque directo"),
                    ClaimFact("traffic_light", "rojo", "A", "A tenía rojo"),
                ),
                InterviewPlan(
                    "coverage_gap",
                    terminal_reason=(
                        "El manual indexado no contiene una regla verificable para estas versiones."
                    ),
                ),
            )
        ),
        retriever=_Retriever(),
        evidence_repository=_Evidence(
            PageEvidence("manual:page:56", "a" * 64, 56, "texto", None, None, ())
        ),
    )

    execution = asyncio.run(workflow.run(ClaimInput("Dos vehículos chocaron en un cruce.")))

    assert execution.needs_input is False
    assert execution.result.blocks[0].text.startswith("El manual indexado")


# --------------------------------------------------------------------------
# El flujo de siniestros tiene que llegar a la tabla de culpabilidad CIDE.
#
# La tabla estaba transcrita y atestada, y `lookup_daa_matrix` probado, pero el
# grafo nunca la consultaba: un siniestro con las casillas del apartado 12
# declaradas se quedaba en «Convenio aplicable, culpabilidad sin determinar»
# para siempre. Estas pruebas fijan el recorrido completo y, sobre todo, dónde
# NO debe resolver.
# --------------------------------------------------------------------------


_PAGE_101 = "sha256:" + "b" * 64 + ":page:101"


_MATRIX_RULE = LoadedRule(
    rule_id="cide-matrix-lookup",
    kind="matrix_lookup",
    description="Tabla de culpabilidad CIDE.",
    prerequisites=("daa_box_a", "daa_box_b", "daa_section_12_only"),
    outcome="Las cruces marcadas determinan la responsabilidad según la tabla.",
    evidence_ids=(_PAGE_101,),
    convention="CIDE",
)

_CELLS = {
    (2, 9): MatrixCell(2, 9, "B", (_PAGE_101,)),  # A1 + B8 → culpable B
    (1, 2): MatrixCell(1, 2, "-", (_PAGE_101,)),  # A0 + B1 → sin atribución
    (3, 5): MatrixCell(3, 5, "B*", (_PAGE_101,)),  # A2 + B4 → observación
}

_EXCEPTIONS = (
    MatrixException(
        note_id="obs-a2-b4",
        text="A2 + B4 = Culpable B, salvo que el A abra la puerta.",
        positions=((3, 5),),
        fact="door_opened_by",
        actor="A",
        liable_unless_exception="B",
        evidence_ids=(_PAGE_101,),
    ),
)


def _run(facts: tuple[ClaimFact, ...]) -> ClaimExecution:
    workflow = LangGraphClaimWorkflow(
        fact_extractor=_Extractor(ExtractedClaimFacts(("A", "B"), facts, InterviewPlan("ready"))),
        retriever=_Retriever("Tabla de culpabilidad CIDE."),
        evidence_repository=_Evidence(
            PageEvidence("manual:page:56", "a" * 64, 56, "texto", None, None, ())
        ),
        rules=(_MATRIX_RULE,),
        matrix_cells=_CELLS,
        matrix_exceptions=_EXCEPTIONS,
    )
    return asyncio.run(workflow.run(ClaimInput("Parte amistoso con el apartado 12 marcado.")))


def _base_facts(**boxes: str) -> tuple[ClaimFact, ...]:
    declared = {"daa_box_a": "A1", "daa_box_b": "B8", **boxes}
    return (
        ClaimFact("vehicle_count", "2", None, "dos vehículos"),
        ClaimFact("direct_collision", "true", None, "colisión directa"),
        ClaimFact("daa_section_12_only", "true", None, "sólo el apartado 12"),
        *(ClaimFact(name, value, None, f"casilla {value}") for name, value in declared.items()),
    )


def test_a_declared_daa_pair_resolves_the_claim_by_the_cide_table() -> None:
    result = _run(_base_facts()).result

    assert result.applicability == "applicable"
    assert result.convention == "CIDE"
    assert result.decision == "resolved"
    assert any(
        evaluation.rule_id == "cide-matrix-lookup" and evaluation.result == "matched"
        for evaluation in result.rules_evaluated
    )
    narrative = " ".join(block.text for block in result.blocks)
    assert "B" in narrative
    assert any(_PAGE_101 in block.evidence_ids for block in result.blocks)


def test_a_narrative_without_declared_boxes_never_resolves_by_the_table() -> None:
    """La matriz sigue protegida: sin casillas declaradas no se aplica."""
    facts = (
        ClaimFact("vehicle_count", "2", None, "dos vehículos"),
        ClaimFact("direct_collision", "true", None, "colisión directa"),
    )
    result = _run(facts).result

    assert result.decision != "resolved"
    assert all(
        evaluation.result != "matched"
        for evaluation in result.rules_evaluated
        if evaluation.rule_id == "cide-matrix-lookup"
    )


def test_a_dash_cell_does_not_resolve_and_says_the_table_attributes_nothing() -> None:
    result = _run(_base_facts(daa_box_a="A0", daa_box_b="B1")).result

    assert result.decision != "resolved"
    narrative = " ".join(block.text for block in result.blocks)
    assert "no atribuye" in narrative.lower()


def test_a_starred_cell_asks_for_its_observation_before_deciding() -> None:
    result = _run(_base_facts(daa_box_a="A2", daa_box_b="B4")).result

    assert result.decision == "conditional"
    assert result.conditions
    assert any("puerta" in condition.lower() for condition in result.conditions)


def test_a_starred_cell_resolves_when_the_observation_is_ruled_out() -> None:
    result = _run(_base_facts(daa_box_a="A2", daa_box_b="B4", door_opened_by="B")).result

    assert result.decision == "resolved"
    assert result.convention == "CIDE"


def test_a_starred_cell_withdraws_the_attribution_when_the_observation_holds() -> None:
    result = _run(_base_facts(daa_box_a="A2", daa_box_b="B4", door_opened_by="A")).result

    assert result.decision != "resolved"
    narrative = " ".join(block.text for block in result.blocks)
    assert "salvo que el A abra la puerta" in narrative


# --------------------------------------------------------------------------
# El flujo de siniestros resuelve con las normas subsidiarias recién conectadas.
#
# A diferencia de `test_claim_workflow_matrix.py`, aquí se carga el artefacto
# firmado real (`load_rules_artifacts`), no un `LoadedRule` construido a mano:
# esto comprueba que el `applies_when` tal y como está escrito en
# `data/rules/ruleset.v1.json` produce el resultado correcto a través del grafo
# completo, no sólo en el evaluador aislado.
# --------------------------------------------------------------------------


_REPO = Path(__file__).resolve().parents[2]
_DOCUMENT_HASH = "b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344"


@dataclass
class _FactsExtractor(ClaimFactExtractor):
    facts: tuple[ClaimFact, ...]
    parties: tuple[str, ...] = ("A", "B")

    async def extract(self, claim: ClaimInput) -> ExtractedClaimFacts:
        return ExtractedClaimFacts(self.parties, self.facts, InterviewPlan("ready"))


def _run_shipped(facts: tuple[ClaimFact, ...]) -> ClaimExecution:
    artifacts = load_rules_artifacts(
        _REPO / "data" / "rules",
        expected_document_hash=_DOCUMENT_HASH,
        evidence_roots=(_REPO / "data" / "extractions",),
    )
    workflow = LangGraphClaimWorkflow(
        fact_extractor=_FactsExtractor(facts),
        retriever=_Retriever("Normas subsidiarias ASCIDE."),
        evidence_repository=_Evidence(
            PageEvidence("manual:page:56", "a" * 64, 56, "texto", None, None, ())
        ),
        rules=artifacts.rules,
        matrix_cells=artifacts.matrix_cells,
        matrix_exceptions=artifacts.matrix_exceptions,
    )
    return asyncio.run(workflow.run(ClaimInput("Relato de prueba.")))


def _base(**extra: str) -> tuple[ClaimFact, ...]:
    values = {"vehicle_count": "2", "direct_collision": "true", **extra}
    return tuple(ClaimFact(name, value, None, value) for name, value in values.items())


def test_parked_vehicle_resolves_to_the_colliding_vehicle() -> None:
    result = _run_shipped(
        _base(
            one_vehicle_parked="true", collision_with_parked_vehicle="true", colliding_vehicle="B"
        )
    ).result

    assert result.applicability == "applicable"
    assert result.convention == "ASCIDE"
    assert result.decision == "resolved"
    assert any(
        evaluation.rule_id == "ascide-b5-parked-vehicle" and evaluation.result == "matched"
        for evaluation in result.rules_evaluated
    )


def test_exit_from_parking_resolves_to_the_exiting_vehicle() -> None:
    result = _run_shipped(
        _base(exit_manoeuvre_by="A", exit_disputed_as_incorporation="false")
    ).result

    assert result.decision == "resolved"
    assert result.convention == "ASCIDE"


def test_exit_from_parking_defers_when_disputed_as_incorporation() -> None:
    """El manual remite esta excepción a otro apartado no verificado."""
    result = _run_shipped(
        _base(exit_manoeuvre_by="A", exit_disputed_as_incorporation="true")
    ).result

    assert result.decision != "resolved"


def test_reverse_vs_rear_impact_resolves_to_the_front_damage_vehicle() -> None:
    result = _run_shipped(_base(contradictory_versions="true", front_damage_vehicle="A")).result

    assert result.decision == "resolved"
    assert result.convention == "ASCIDE"


def test_door_opening_resolves_only_without_a_specified_action() -> None:
    result = _run_shipped(
        _base(door_involved="true", door_opening_specified="false", door_vehicle="B")
    ).result

    assert result.decision == "resolved"
    assert result.convention == "CIDE"


def test_door_opening_defers_when_the_action_is_specified() -> None:
    result = _run_shipped(
        _base(door_involved="true", door_opening_specified="true", door_vehicle="B")
    ).result

    assert result.decision != "resolved"


# --------------------------------------------------------------------------
# Verify the Langfuse ``CallbackHandler`` is wired into the claim workflow.
#
# Oracle G4 finding #2: ``LangGraphClaimWorkflow`` did not accept a
# ``callback_factory``, so claim traces returned 0 observations in
# Langfuse. After the fix the constructor accepts the same factory the
# question workflow already takes; passing it must make the graph dispatch
# the returned handler through ``RunnableConfig.callbacks`` so the
# Langfuse ``CallbackHandler`` attaches its spans to the running trace.
# --------------------------------------------------------------------------


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
