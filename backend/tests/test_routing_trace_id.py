"""The auto path must produce trace ids Langfuse actually accepts.

Langfuse trace ids are 32 lowercase hex characters. The routing workflow
defaulted to ``uuid.uuid4()``, whose dashes make it invalid, so the SDK logged
"Passed trace ID ... is not a valid 32 lowercase hex char Langfuse trace id.
Ignoring trace ID." and the envelope built a link that could never resolve.
"""

import inspect
import re

from infrastructure.adapters.outbound.query_workflow.langgraph_workflow import (
    LangGraphResolveQuery,
)

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
