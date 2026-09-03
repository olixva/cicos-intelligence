"""Enrutado automatico: servicio, clasificador LLM, presupuesto de tiempo y trazas."""

from __future__ import annotations

import asyncio
import inspect
import re
from dataclasses import dataclass, field
from typing import Any, cast

import pytest

from application.models.claim import ClaimExecution
from application.models.query import (
    AnswerBlock,
    QueryExecution,
    QueryInput,
    QuestionAnswer,
)
from application.ports.outbound.language_model import (
    LanguageModelError,
    MissingLanguageModelCredentialsError,
    ModelOutputError,
    ModelTimeoutError,
)
from application.services.routing import (
    RouteExecutionError,
    resolve_query,
)
from domain.models.decision import ClaimAnalysis
from domain.models.routing import (
    ClarificationResult,
    RouteClassification,
)
from domain.models.rule_evaluation import RuleEvaluation
from infrastructure.adapters.outbound.claim_workflow.langgraph_workflow import (
    LangGraphClaimWorkflow,
)
from infrastructure.adapters.outbound.language_model.openai_routing_language_model import (
    OpenAIRoutingLanguageModel,
    ParsedRoutingResponse,
    RouteDecisionSchema,
    RoutingPrompt,
    RoutingTransport,
)
from infrastructure.adapters.outbound.query_workflow.langgraph_workflow import (
    DEFAULT_ROUTING_TIMEOUT_SECONDS,
    LangGraphResolveQuery,
    build_resolve_query_workflow,
    routing_metadata,
)
from infrastructure.adapters.outbound.question_workflow.langgraph_workflow import (
    LangGraphQuestionWorkflow,
)

# --------------------------------------------------------------------------
# Closed-enum auto-router dispatch service.
#
# These tests pin the counter invariants the design requires: each query
# runs through exactly one downstream flow. ``clarification_required``
# must execute neither; an unsupported classifier output must raise
# ``RouteExecutionError`` before any dispatch attempt.
#
# The repo convention runs async test bodies via ``asyncio.run`` inside
# ``def`` tests rather than ``async def``; we follow that pattern here.
# --------------------------------------------------------------------------


@dataclass
class _CounterAnswerQuestion:
    calls: int = 0
    payload: QueryExecution = field(
        default_factory=lambda: QueryExecution(
            result=QuestionAnswer("answered", (AnswerBlock("ok", ("sha256:x:page:1",)),)),
            context=(),
            trace_id="trace-q",
        )
    )

    async def execute(self, query: QueryInput) -> QueryExecution:
        self.calls += 1
        return self.payload


@dataclass
class _CounterAnalyzeClaim:
    calls: int = 0
    payload: ClaimExecution = field(
        default_factory=lambda: ClaimExecution(
            result=ClaimAnalysis(
                applicability="applicable",
                convention="CIDE",
                decision="resolved",
                party_ids=("A", "B"),
                facts=(),
                contradictions=(),
                conditions=(),
                missing_information=(),
                blocks=(),
                rules_evaluated=(
                    RuleEvaluation(
                        rule_id="cide-requires-two-vehicles",
                        inputs=(("vehicle_count", "2"),),
                        result="matched",
                        evidence_ids=("sha256:" + "b" * 64 + ":page:56",),
                        rationale="Dos vehículos con colisión directa.",
                    ),
                ),
            ),
            context=(),
            trace_id="trace-c",
        )
    )

    async def execute(self, claim) -> ClaimExecution:  # type: ignore[no-untyped-def]
        self.calls += 1
        return self.payload


@dataclass
class _StubClassifier:
    classification: RouteClassification

    async def classify(self, query: QueryInput) -> RouteClassification:
        return self.classification


class _BoomAnswerQuestion:
    async def execute(self, query: QueryInput) -> QueryExecution:
        raise RuntimeError("provider exploded")


class _BoomAnalyzeClaim:
    async def execute(self, claim) -> ClaimExecution:  # type: ignore[no-untyped-def]
        raise RuntimeError("provider exploded")


def _query() -> QueryInput:
    return QueryInput(text="¿Qué dice el manual sobre CIDE?", language="es")


def test_resolve_query_dispatches_question_exactly_once() -> None:
    answer = _CounterAnswerQuestion()
    claim = _CounterAnalyzeClaim()
    classifier = _StubClassifier(RouteClassification("question"))

    execution = asyncio.run(resolve_query(_query(), classifier, answer, claim))

    assert execution.classification.decision == "question"
    assert isinstance(execution.dispatch, QueryExecution)
    assert answer.calls == 1
    assert claim.calls == 0
    assert execution.trace_id == "trace-q"


def test_resolve_query_dispatches_claim_exactly_once() -> None:
    answer = _CounterAnswerQuestion()
    claim = _CounterAnalyzeClaim()
    classifier = _StubClassifier(RouteClassification("claim"))

    execution = asyncio.run(resolve_query(_query(), classifier, answer, claim))

    assert execution.classification.decision == "claim"
    assert isinstance(execution.dispatch, ClaimExecution)
    assert answer.calls == 0
    assert claim.calls == 1
    assert execution.trace_id == "trace-c"


def test_resolve_query_clarification_executes_no_flow() -> None:
    answer = _CounterAnswerQuestion()
    claim = _CounterAnalyzeClaim()
    classifier = _StubClassifier(
        RouteClassification("clarification_required", rationale="faltan datos")
    )

    execution = asyncio.run(resolve_query(_query(), classifier, answer, claim))

    assert execution.classification.decision == "clarification_required"
    assert isinstance(execution.dispatch, ClarificationResult)
    assert execution.dispatch.message == "faltan datos"
    assert answer.calls == 0
    assert claim.calls == 0
    assert execution.trace_id is not None  # uuid synthesized


def test_resolve_query_clarification_falls_back_to_default_message() -> None:
    answer = _CounterAnswerQuestion()
    claim = _CounterAnalyzeClaim()
    classifier = _StubClassifier(RouteClassification("clarification_required"))

    execution = asyncio.run(resolve_query(_query(), classifier, answer, claim))

    assert isinstance(execution.dispatch, ClarificationResult)
    assert "Necesito más información" in execution.dispatch.message


def test_resolve_query_rejects_unsupported_decision() -> None:
    classifier = _StubClassifier(RouteClassification("nonsense"))  # type: ignore[arg-type]
    answer = _CounterAnswerQuestion()
    claim = _CounterAnalyzeClaim()

    with pytest.raises(RouteExecutionError, match="unsupported routing decision"):
        asyncio.run(resolve_query(_query(), classifier, answer, claim))


def test_resolve_query_wraps_provider_error_from_answer_flow() -> None:
    classifier = _StubClassifier(RouteClassification("question"))

    with pytest.raises(RouteExecutionError, match="routing flow raised RuntimeError"):
        asyncio.run(
            resolve_query(_query(), classifier, _BoomAnswerQuestion(), _CounterAnalyzeClaim())
        )


def test_resolve_query_wraps_provider_error_from_claim_flow() -> None:
    classifier = _StubClassifier(RouteClassification("claim"))

    with pytest.raises(RouteExecutionError, match="routing flow raised RuntimeError"):
        asyncio.run(
            resolve_query(_query(), classifier, _CounterAnswerQuestion(), _BoomAnalyzeClaim())
        )


# ---------------------------------------------------------------------------
# Override heurístico: el router barato (gpt-5.6-luna) puede clasificar
# un relato de siniestro como 'clarification_required' o 'question' por
# confundir palabras incidentales (p. ej. "no consigue detenerse a
# tiempo" → pregunta sobre el tiempo) con la intención real. Si el texto
# tiene vocabulario típico de relato de siniestro, forzamos 'claim'.
# ---------------------------------------------------------------------------


def test_resolve_query_overrides_clarification_to_claim_on_vehicle_collision() -> None:
    """Caso real reportado: el router barato clasifica un alcance
    trasero como 'clarification_required' porque la frase incluye
    "no consigue detenerse a tiempo", que el modelo entiende como
    pregunta sobre el tiempo meteorológico o la hora. La heurística
    detecta vehículos etiquetados + vocabulario de colisión + semáforo
    y fuerza 'claim' para que el análisis corra sobre el texto."""

    claim_text = (
        "El vehículo A está detenido ante un semáforo en rojo cuando el "
        "vehículo B no consigue detenerse a tiempo y choca por detrás "
        "contra el vehículo A. Ambos conductores afirman que estaban "
        "prestando atención, pero el conductor del vehículo B insiste "
        "en que el vehículo A frenó de forma repentina."
    )
    answer = _CounterAnswerQuestion()
    claim = _CounterAnalyzeClaim()
    classifier = _StubClassifier(
        RouteClassification("clarification_required", rationale="pide hora")
    )
    query = QueryInput(text=claim_text, language="es")

    execution = asyncio.run(resolve_query(query, classifier, answer, claim))

    assert execution.classification.decision == "claim"
    assert "Heur" in (execution.classification.rationale or "")
    assert isinstance(execution.dispatch, ClaimExecution)
    assert answer.calls == 0
    assert claim.calls == 1
    assert execution.trace_id == "trace-c"


def test_resolve_query_overrides_question_to_claim_on_collision_narrative() -> None:
    """Si el router decide 'question' para un texto que claramente
    describe una colisión, también override."""

    answer = _CounterAnswerQuestion()
    claim = _CounterAnalyzeClaim()
    classifier = _StubClassifier(RouteClassification("question"))
    query = QueryInput(
        text=(
            "El vehículo A y el vehículo B chocan en un cruce. ¿Quién "
            "es culpable? Ambos dicen que tenían semáforo en verde."
        ),
        language="es",
    )

    execution = asyncio.run(resolve_query(query, classifier, answer, claim))

    assert execution.classification.decision == "claim"
    assert isinstance(execution.dispatch, ClaimExecution)
    assert claim.calls == 1
    assert answer.calls == 0


def test_resolve_query_keeps_question_for_actual_questions() -> None:
    """La heurística no afecta a preguntas reales: una pregunta al
    manual con vocabulario de incidente incidental no debe override."""

    answer = _CounterAnswerQuestion()
    claim = _CounterAnalyzeClaim()
    classifier = _StubClassifier(RouteClassification("question"))
    query = QueryInput(text="¿Qué dice el manual sobre CIDE?", language="es")

    execution = asyncio.run(resolve_query(query, classifier, answer, claim))

    assert execution.classification.decision == "question"
    assert isinstance(execution.dispatch, QueryExecution)
    assert answer.calls == 1
    assert claim.calls == 0


def test_resolve_query_keeps_clarification_for_genuinely_ambiguous_input() -> None:
    """Texto corto sin vocabulario de relato no debe override aunque
    el router diga clarification_required. La heurística mira 2+
    marcadores típicos, no sólo presencia de 'vehículo'."""

    answer = _CounterAnswerQuestion()
    claim = _CounterAnalyzeClaim()
    classifier = _StubClassifier(
        RouteClassification("clarification_required", rationale="faltan datos")
    )
    query = QueryInput(text="hola", language="es")

    execution = asyncio.run(resolve_query(query, classifier, answer, claim))

    assert execution.classification.decision == "clarification_required"
    assert isinstance(execution.dispatch, ClarificationResult)
    assert answer.calls == 0
    assert claim.calls == 0


# --------------------------------------------------------------------------
# Dedicated routing classifier for the auto router.
#
# The router cannot reuse the question-flow ``OpenAILanguageModel`` because
# its ``text_format=AnswerSchema`` constrains the status literal to the
# four ``AnswerStatus`` values and provides no path for the model to
# emit ``claim`` or ``clarification_required``. These tests pin the
# dedicated ``OpenAIRoutingLanguageModel`` schema, validation and error
# shapes.
# --------------------------------------------------------------------------


def _prompt() -> RoutingPrompt:
    return RoutingPrompt(name="auto-router", version=1, content="Clasifica la consulta.")


def _manual_query() -> QueryInput:
    return QueryInput(text="¿Qué dice el manual?", language="es")


@dataclass
class _FakeParsedResponse(ParsedRoutingResponse):
    parsed: RouteDecisionSchema | None
    response_status: str = "completed"

    @property
    def output_parsed(self) -> object | None:
        return self.parsed

    @property
    def status(self) -> str:
        return self.response_status


@dataclass
class _FakeTransport(RoutingTransport):
    """Records the last call and returns a configurable parsed response."""

    parsed: RouteDecisionSchema | None = None
    response_status: str = "completed"
    raise_exc: Exception | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def parse(
        self,
        *,
        model: str,
        input: Any,
        text_format: type[RouteDecisionSchema],
        store: bool,
        timeout: float,
    ) -> ParsedRoutingResponse:
        self.calls.append(
            {"model": model, "text_format": text_format, "store": store, "timeout": timeout}
        )
        if self.raise_exc is not None:
            raise self.raise_exc
        return _FakeParsedResponse(parsed=self.parsed, response_status=self.response_status)


def test_router_classifier_returns_question_decision() -> None:
    transport = _FakeTransport(
        parsed=RouteDecisionSchema(decision="question", rationale="answered"),
    )
    classifier = OpenAIRoutingLanguageModel(
        model="gpt-5.4", prompt=_prompt(), transport=cast(Any, transport)
    )

    classification = asyncio.run(classifier.classify(_manual_query()))

    assert classification == RouteClassification(decision="question", rationale="answered")
    assert len(transport.calls) == 1
    assert transport.calls[0]["text_format"] is RouteDecisionSchema


def test_router_classifier_returns_claim_decision() -> None:
    transport = _FakeTransport(
        parsed=RouteDecisionSchema(decision="claim", rationale="narrative"),
    )
    classifier = OpenAIRoutingLanguageModel(
        model="gpt-5.4", prompt=_prompt(), transport=cast(Any, transport)
    )

    classification = asyncio.run(classifier.classify(_manual_query()))

    assert classification == RouteClassification(decision="claim", rationale="narrative")


def test_router_classifier_returns_clarification_decision() -> None:
    transport = _FakeTransport(
        parsed=RouteDecisionSchema(decision="clarification_required", rationale="faltan datos"),
    )
    classifier = OpenAIRoutingLanguageModel(
        model="gpt-5.4", prompt=_prompt(), transport=cast(Any, transport)
    )

    classification = asyncio.run(classifier.classify(_manual_query()))

    assert classification == RouteClassification(
        decision="clarification_required", rationale="faltan datos"
    )


def test_router_classifier_rejects_none_parsed() -> None:
    transport = _FakeTransport(parsed=None)
    classifier = OpenAIRoutingLanguageModel(
        model="gpt-5.4", prompt=_prompt(), transport=cast(Any, transport)
    )

    with pytest.raises(ModelOutputError, match="invalid decision"):
        asyncio.run(classifier.classify(_manual_query()))


def test_router_classifier_rejects_incomplete_response_status() -> None:
    transport = _FakeTransport(
        parsed=RouteDecisionSchema(decision="question", rationale=None),
        response_status="incomplete",
    )
    classifier = OpenAIRoutingLanguageModel(
        model="gpt-5.4", prompt=_prompt(), transport=cast(Any, transport)
    )

    with pytest.raises(ModelOutputError, match="incomplete"):
        asyncio.run(classifier.classify(_manual_query()))


def test_router_classifier_wraps_timeout_as_model_timeout_error() -> None:
    import openai

    transport = _FakeTransport(raise_exc=openai.APITimeoutError(request=None))  # type: ignore[arg-type]
    classifier = OpenAIRoutingLanguageModel(
        model="gpt-5.4", prompt=_prompt(), transport=cast(Any, transport)
    )

    with pytest.raises(ModelTimeoutError):
        asyncio.run(classifier.classify(_manual_query()))


def test_router_classifier_wraps_api_error_as_language_model_error() -> None:
    import openai

    transport = _FakeTransport(
        raise_exc=openai.APIError(message="boom", request=None, body=None)  # type: ignore[arg-type]
    )
    classifier = OpenAIRoutingLanguageModel(
        model="gpt-5.4", prompt=_prompt(), transport=cast(Any, transport)
    )

    with pytest.raises(LanguageModelError):
        asyncio.run(classifier.classify(_manual_query()))


def test_router_classifier_raises_when_openai_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    classifier = OpenAIRoutingLanguageModel(model="gpt-5.4", prompt=_prompt())

    with pytest.raises(MissingLanguageModelCredentialsError):
        asyncio.run(classifier.classify(_manual_query()))


def test_router_classifier_rejects_empty_model_at_construction() -> None:
    with pytest.raises(ValueError, match="routing model must be nonempty"):
        OpenAIRoutingLanguageModel(model="", prompt=_prompt())


def test_router_classifier_rejects_nonpositive_timeout() -> None:
    with pytest.raises(ValueError, match="timeout must be positive"):
        OpenAIRoutingLanguageModel(model="gpt-5.4", prompt=_prompt(), timeout_seconds=0)


def test_routing_prompt_rejects_empty_content() -> None:
    with pytest.raises(ValueError, match="nonempty"):
        RoutingPrompt(name="auto-router", version=1, content="")


def test_routing_prompt_rejects_nonpositive_version() -> None:
    with pytest.raises(ValueError, match="positive integer"):
        RoutingPrompt(name="auto-router", version=0, content="hola")


# --------------------------------------------------------------------------
# The router's timeout must contain the workflows it dispatches to.
#
# The routing workflow wraps classification AND the full question or claim
# execution in one ``asyncio.timeout``. Its budget was 20s while the question
# workflow allows 45s and the claim workflow 30s, so an auto-mode request could
# never use the time the inner workflow was entitled to: it failed with
# "routing workflow timed out" before the answer came back. The user saw
# "Error desconocido" in the interface and no answer at all.
# --------------------------------------------------------------------------


def _default(cls: type, name: str = "timeout_seconds") -> float:
    """Read a constructor's declared default timeout."""
    import inspect

    return inspect.signature(cls.__init__).parameters[name].default


def test_routing_budget_exceeds_the_question_workflow_budget() -> None:
    inner = _default(LangGraphQuestionWorkflow)
    assert DEFAULT_ROUTING_TIMEOUT_SECONDS > inner, (
        f"the router allows {DEFAULT_ROUTING_TIMEOUT_SECONDS}s but contains a "
        f"question workflow allowed {inner}s"
    )


def test_routing_budget_exceeds_the_claim_workflow_budget() -> None:
    inner = _default(LangGraphClaimWorkflow)
    assert DEFAULT_ROUTING_TIMEOUT_SECONDS > inner, (
        f"the router allows {DEFAULT_ROUTING_TIMEOUT_SECONDS}s but contains a "
        f"claim workflow allowed {inner}s"
    )


def test_routing_budget_leaves_room_for_the_classification_itself() -> None:
    """The router also spends time classifying before it dispatches."""
    slowest_inner = max(
        _default(LangGraphQuestionWorkflow),
        _default(LangGraphClaimWorkflow),
    )
    assert DEFAULT_ROUTING_TIMEOUT_SECONDS >= slowest_inner + 10.0


@pytest.mark.parametrize("budget", [0, -1])
def test_routing_rejects_a_nonpositive_budget(budget: float) -> None:
    from infrastructure.adapters.outbound.query_workflow.langgraph_workflow import (
        build_resolve_query_workflow,
    )

    with pytest.raises(ValueError, match="timeout"):
        build_resolve_query_workflow(
            classifier=object(),  # type: ignore[arg-type]
            answer_question=object(),  # type: ignore[arg-type]
            analyze_claim=object(),  # type: ignore[arg-type]
            timeout_seconds=budget,
        )


def test_asyncio_timeout_semantics_are_what_the_budget_assumes() -> None:
    """Guard the assumption: an outer timeout smaller than an inner one wins."""

    async def scenario() -> str:
        try:
            async with asyncio.timeout(0.02):
                async with asyncio.timeout(1.0):
                    await asyncio.sleep(0.5)
        except TimeoutError:
            return "outer-wins"
        return "completed"

    assert asyncio.run(scenario()) == "outer-wins"


# --------------------------------------------------------------------------
# The auto path must produce trace ids Langfuse actually accepts.
#
# Langfuse trace ids are 32 lowercase hex characters. The routing workflow
# defaulted to ``uuid.uuid4()``, whose dashes make it invalid, so the SDK logged
# "Passed trace ID ... is not a valid 32 lowercase hex char Langfuse trace id.
# Ignoring trace ID." and the envelope built a link that could never resolve.
# --------------------------------------------------------------------------


_LANGFUSE_TRACE_ID = re.compile(r"^[0-9a-f]{32}$")


def test_routing_workflow_does_not_invent_a_trace_id_by_default() -> None:
    """No factory means no trace, never a fabricated id Langfuse will reject."""
    workflow = LangGraphResolveQuery(
        classifier=object(),  # type: ignore[arg-type]
        answer_question=object(),  # type: ignore[arg-type]
        analyze_claim=object(),  # type: ignore[arg-type]
    )
    produced = workflow._trace_id_factory()  # pyright: ignore[reportPrivateUsage]
    assert produced is None, f"default factory produced {produced!r}"


def test_a_supplied_factory_is_used_verbatim() -> None:
    workflow = LangGraphResolveQuery(
        classifier=object(),  # type: ignore[arg-type]
        answer_question=object(),  # type: ignore[arg-type]
        analyze_claim=object(),  # type: ignore[arg-type]
        trace_id_factory=lambda: "0" * 32,
    )
    produced = workflow._trace_id_factory()  # pyright: ignore[reportPrivateUsage]
    assert produced is not None and _LANGFUSE_TRACE_ID.match(produced)


def test_bootstrap_wires_the_langfuse_trace_id_factory_into_the_router() -> None:
    """The other two builders pass create_trace_id; the router must too."""
    import bootstrap

    source = inspect.getsource(bootstrap.build_resolve_query)
    assert "trace_id_factory" in source, (
        "build_resolve_query does not pass a trace_id_factory, so the auto path "
        "falls back to a non-Langfuse id and its trace link cannot resolve"
    )
    assert "create_trace_id" in source


# --------------------------------------------------------------------------
# LangGraph closed-enum selector end-to-end tests.
#
# Each test runs a real ``StateGraph.ainvoke`` via ``asyncio.run`` against
# explicit fakes; no live OpenAI, Langfuse or Qdrant is touched. The
# counter invariants established in ``test_query_routing.py`` are mirrored
# here at the graph-level dispatch boundary.
#
# The repo convention runs async test bodies via ``asyncio.run`` inside
# ``def`` tests rather than ``async def``; we follow that pattern here.
# --------------------------------------------------------------------------


def _plain_query() -> QueryInput:
    return QueryInput(text="texto de prueba", language="es")


def test_build_resolve_query_workflow_compiles() -> None:
    workflow = build_resolve_query_workflow(
        classifier=_StubClassifier(RouteClassification("question")),
        answer_question=_CounterAnswerQuestion(),
        analyze_claim=_CounterAnalyzeClaim(),
    )
    assert isinstance(workflow, LangGraphResolveQuery)


def test_graph_routes_question_branch() -> None:
    answer = _CounterAnswerQuestion()
    claim = _CounterAnalyzeClaim()
    workflow = build_resolve_query_workflow(
        classifier=_StubClassifier(RouteClassification("question")),
        answer_question=answer,
        analyze_claim=claim,
    )
    execution = asyncio.run(workflow.execute(_plain_query()))

    assert execution.classification.decision == "question"
    assert isinstance(execution.dispatch, QueryExecution)
    assert answer.calls == 1
    assert claim.calls == 0


def test_graph_routes_claim_branch() -> None:
    answer = _CounterAnswerQuestion()
    claim = _CounterAnalyzeClaim()
    workflow = build_resolve_query_workflow(
        classifier=_StubClassifier(RouteClassification("claim")),
        answer_question=answer,
        analyze_claim=claim,
    )
    execution = asyncio.run(workflow.execute(_plain_query()))

    assert execution.classification.decision == "claim"
    assert isinstance(execution.dispatch, ClaimExecution)
    assert answer.calls == 0
    assert claim.calls == 1


def test_graph_routes_clarification_branch() -> None:
    answer = _CounterAnswerQuestion()
    claim = _CounterAnalyzeClaim()
    workflow = build_resolve_query_workflow(
        classifier=_StubClassifier(
            RouteClassification("clarification_required", rationale="necesito datos")
        ),
        answer_question=answer,
        analyze_claim=claim,
    )
    execution = asyncio.run(workflow.execute(_plain_query()))

    assert execution.classification.decision == "clarification_required"
    assert isinstance(execution.dispatch, ClarificationResult)
    assert execution.dispatch.message == "necesito datos"
    assert answer.calls == 0
    assert claim.calls == 0


def test_routing_metadata_defaults_match_module_state() -> None:
    """The module-level ``_ROUTING_METADATA`` captures the env at import time."""

    metadata = routing_metadata()
    assert metadata["langfuse_prompt_name"] == "auto-router"
    assert isinstance(metadata["langfuse_prompt_version"], int)
    assert metadata["langfuse_prompt_version"] >= 1
    assert isinstance(metadata["model_name"], str)
    assert metadata["model_name"] != ""


def test_auto_router_attaches_session_and_self_describing_run_metadata() -> None:
    """A missing router session would split one user conversation in Langfuse."""

    class _GraphCapture:
        config: dict[str, Any] | None = None

        async def ainvoke(self, state: Any, *, config: dict[str, Any]) -> dict[str, Any]:
            self.config = config
            return {
                "classification": RouteClassification("clarification_required", "faltan datos"),
                "dispatch": ClarificationResult("faltan datos"),
            }

    workflow = build_resolve_query_workflow(
        classifier=_StubClassifier(RouteClassification("clarification_required")),
        answer_question=_CounterAnswerQuestion(),
        analyze_claim=_CounterAnalyzeClaim(),
    )
    graph = _GraphCapture()
    workflow._graph = graph  # pyright: ignore[reportPrivateUsage]

    asyncio.run(
        workflow.execute(
            QueryInput("texto de prueba", "es", session_id="session-observability-test")
        )
    )

    assert graph.config is not None
    assert graph.config["run_name"] == "allianz_auto_router"
    assert graph.config["tags"] == ["allianz", "workflow:auto_router"]
    assert graph.config["metadata"] == {
        "langfuse_session_id": "session-observability-test",
        "session_id": "session-observability-test",
        "allianz_workflow": "auto_router",
    }
