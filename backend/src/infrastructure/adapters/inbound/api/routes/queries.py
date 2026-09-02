"""Auto-router HTTP endpoint and unified envelope for the three modes.

The router exposes two endpoints under ``/api/v1/queries``:

- ``POST /resolve`` — the closed-enum auto router (added in Phase 3).
- ``POST /`` — the unified envelope that dispatches ``text`` to one of
  the three flows based on the body's ``mode`` field. ``mode=question``
  goes straight to the explicit question port; ``mode=claim`` goes
  straight to the explicit claim port; ``mode=auto`` invokes the
  router. The envelope never invokes the router for explicit modes
  (Oracle Gate 1 design rule).
- ``POST /stream`` — bounded Server-Sent-Events stream with the same
  request body, emitting ``started``, ``stage``, ``completed`` and
  ``failed`` events.

The envelope route is mounted only when **all three** ports are
injected into ``create_app``. The streaming route requires
``sse-starlette``; the route factory exposes a sentinel that the app
skips when the dependency is unavailable.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from fastapi import APIRouter

from application.models.query import (
    ContextEvidence,
    QueryInput,
)
from application.ports.inbound.analyze_claim import AnalyzeClaim
from application.ports.inbound.answer_question import AnswerQuestion
from application.ports.inbound.resolve_query import ResolveQuery
from application.services.input_guardrails import guardrail_message
from domain.models.claim import ClaimInput
from infrastructure.adapters.inbound.api.schemas.envelope import (
    EnvelopeRequest,
    EnvelopeResponse,
    EvidenceItem,
)
from infrastructure.adapters.inbound.api.schemas.query import (
    QueryResolveRequest,
    QueryResolveResponse,
)


def build_query_router(resolve_query: ResolveQuery) -> APIRouter:
    """Bind the resolve route solely to the closed-enum auto router port.

    Preserved from Phase 3 (``9c99371`` / ``86638b7``). Mounted only when
    ``resolve_query`` is injected into ``create_app``. The response
    shape is intentionally minimal — the caller receives the selected
    ``decision`` plus a short ``rationale`` and trace identifier.
    """

    router = APIRouter(prefix="/api/v1/queries", tags=["queries"])

    async def resolve_query_route(request: QueryResolveRequest) -> QueryResolveResponse:
        execution = await resolve_query.execute(
            QueryInput(
                text=request.text,
                language=request.language,
                session_id=request.session_id,
            )
        )
        return QueryResolveResponse.from_domain(execution)

    router.add_api_route(
        "/resolve",
        resolve_query_route,
        methods=["POST"],
        response_model=QueryResolveResponse,
    )
    return router


def _query_input_from_request(request: EnvelopeRequest) -> QueryInput:
    return QueryInput(text=request.text, language=request.language, session_id=request.session_id)


def _claim_input_from_request(request: EnvelopeRequest) -> ClaimInput:
    clarifications = request.clarifications or ()
    return ClaimInput(
        text=request.text,
        language=request.language,
        clarifications=clarifications,
        session_id=request.session_id,
        thread_id=request.thread_id,
        resume=request.resume,
    )


async def _execute_envelope(
    request: EnvelopeRequest,
    *,
    answer_question: AnswerQuestion,
    analyze_claim: AnalyzeClaim,
    resolve_query: ResolveQuery,
    request_id: str | None = None,
) -> EnvelopeResponse:
    """Dispatch by mode and project into the envelope response.

    Explicit modes bypass the auto router entirely (Oracle Gate 1).

    ``request_id`` is accepted as a parameter so the SSE generator can
    pass the uuid it already emitted in the ``started`` event — Finding
    G2 #2 (single uuid per request across ``started``, envelope and
    ``failed``). When ``None`` (synchronous route) a fresh uuid4 is
    generated here so the response still carries a server-side id.
    """

    rid = request_id or str(uuid.uuid4())

    refusal = guardrail_message(request.text)
    if refusal is not None:
        # Guardrail responses are terminal and deliberately carry no evidence.
        # They apply even when a caller selected an explicit mode: unsafe or
        # unrelated text must not reach retrieval, the classifier, or the LLM.
        from infrastructure.adapters.inbound.api.schemas.envelope import ClarificationResultBody

        return EnvelopeResponse(
            request_id=rid,
            requested_mode=request.mode,
            resolved_mode="clarification",
            result=ClarificationResultBody(kind="clarification", message=refusal),
            metadata={"guardrail": "blocked"},
        )

    if request.mode == "question":
        execution = await answer_question.execute(_query_input_from_request(request))
        return EnvelopeResponse.from_question(
            request_id=rid,
            execution=execution,
            evidence=_evidence_items(execution.context),
        )
    if request.mode == "claim":
        execution = await analyze_claim.execute(_claim_input_from_request(request))
        return EnvelopeResponse.from_claim(
            request_id=rid,
            execution=execution,
            evidence=_evidence_items(execution.context),
        )
    # request.mode == "auto"
    execution = await resolve_query.execute(_query_input_from_request(request))
    # The auto-router's ``RouteExecution`` does not carry its own
    # ``context``; the evidence lives inside the dispatch (which may be
    # a ``QueryExecution`` or ``ClaimExecution``). ``ClarificationResult``
    # carries no context, so we project an empty tuple there.
    context = _context_from_route_execution(execution)
    return EnvelopeResponse.from_route_execution(
        request_id=rid,
        execution=execution,
        evidence=_evidence_items(context),
    )


def _context_from_route_execution(
    execution: object,
) -> tuple[ContextEvidence, ...]:
    """Extract the ``ContextEvidence`` tuple from a ``RouteExecution``.

    Centralised so the envelope route does not depend on the route
    module importing the domain model directly (the route only needs
    the duck-typed contract).
    """

    from application.models.claim import ClaimExecution as _ClaimExecution
    from application.models.query import QueryExecution as _QueryExecution

    dispatch = getattr(execution, "dispatch", None)
    if isinstance(dispatch, (_QueryExecution, _ClaimExecution)):
        return dispatch.context
    return ()


def _evidence_items(context: tuple[ContextEvidence, ...]) -> tuple[EvidenceItem, ...]:
    """Project ``ContextEvidence`` into the envelope evidence shape.

    Drops local asset paths and keeps only the public identity.
    """

    items: list[EvidenceItem] = []
    for entry in context:
        if not entry.sources:
            continue
        first_source = entry.sources[0]
        items.append(
            EvidenceItem(
                evidence_id=entry.evidence_ids[0],
                document_hash=first_source.document_hash,
                pdf_page=first_source.pdf_page,
                delivery=entry.delivery,
            )
        )
    return tuple(items)


def build_envelope_router(
    *,
    answer_question: AnswerQuestion,
    analyze_claim: AnalyzeClaim,
    resolve_query: ResolveQuery,
    allowed_profiles: tuple[str, ...] = (),
) -> APIRouter:
    """Build the envelope router binding the three ports explicitly.

    The router requires all three ports; the composition root decides
    when to mount it (it never mounts the envelope if any port is
    missing). The router ignores ``stream=true`` on the synchronous
    path (the OpenAPI description points to ``/stream`` for that).
    """

    router = APIRouter(prefix="/api/v1/queries", tags=["queries"])

    async def envelope_route(request: EnvelopeRequest) -> EnvelopeResponse:
        if (
            request.profile is not None
            and allowed_profiles
            and (request.profile not in allowed_profiles)
        ):
            # Surface contract: validation only in v1. The envelope
            # accepts the profile string but never reroutes at runtime;
            # an unrecognised profile is rejected with 422.
            from fastapi import HTTPException

            raise HTTPException(
                status_code=422,
                detail={"code": "unsupported_profile", "profile": request.profile},
            )
        return await _execute_envelope(
            request,
            answer_question=answer_question,
            analyze_claim=analyze_claim,
            resolve_query=resolve_query,
        )

    router.add_api_route(
        "",
        envelope_route,
        methods=["POST"],
        response_model=EnvelopeResponse,
        name="envelope",
    )
    return router


async def _streaming_event_loop(
    request: EnvelopeRequest,
    *,
    answer_question: AnswerQuestion,
    analyze_claim: AnalyzeClaim,
    resolve_query: ResolveQuery,
) -> AsyncIterator[dict[str, str]]:
    """Yield the bounded SSE events for the envelope.

    Events follow the plan: ``started`` (request metadata), ``stage``
    (only for ``auto`` mode classification), ``completed`` (terminal
    success body), ``failed`` (terminal failure body). The generator
    NEVER performs an automatic retry; client cancellation simply
    stops the generator.

    Every event carries a fresh ``event_id`` and an ISO-8601
    ``timestamp`` so the client can compute real per-stage durations
    and deduplicate replays. The ``request_id`` is shared by every
    event belonging to the same request so the client can stitch the
    timeline.

    Explicit modes (``question``, ``claim``) NEVER emit a ``stage``
    event; only ``auto`` does, and the event carries the resolved mode
    so the UI never shows ``clasificando`` while the explicit port is
    already running.

    ``sse-starlette.EventSourceResponse`` expects each ``data`` field
    to be a JSON-serialised string; the test driver reads it back
    with ``json.loads``. The string form is the wire contract.
    """

    request_id = str(uuid.uuid4())
    yield {
        "event": "started",
        "data": _json_dumps(
            _event_envelope(
                "started",
                request_id,
                {"mode": request.mode},
            )
        ),
    }

    try:
        response = await _execute_envelope(
            request,
            answer_question=answer_question,
            analyze_claim=analyze_claim,
            resolve_query=resolve_query,
            request_id=request_id,
        )
        if request.mode == "auto" and response.resolved_mode in ("question", "claim"):
            yield _dispatch_event(request_id, response.resolved_mode)
        yield {
            "event": "completed",
            "data": _json_dumps(
                _event_envelope(
                    "completed",
                    request_id,
                    {"response": json.loads(response.model_dump_json())},
                )
            ),
        }
    except Exception as error:  # noqa: BLE001 — surface contract translates everything
        yield {
            "event": "failed",
            "data": _json_dumps(
                _event_envelope(
                    "failed",
                    request_id,
                    {
                        "code": "internal_error",
                        "message": str(error)[:200],
                        "retryable": True,
                    },
                )
            ),
        }


def _event_envelope(name: str, request_id: str, payload: dict[str, object]) -> dict[str, object]:
    """Wrap every SSE event payload with ``event_id`` and ``timestamp``.

    ``event_id`` is a fresh UUID4 so the client can deduplicate replays
    across reconnections. ``timestamp`` is an ISO-8601 UTC stamp so
    real durations are computed from the timeline, not invented by a
    client-side timer.
    """
    return {
        "event": name,
        "request_id": request_id,
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.now(UTC).isoformat(),
        "payload": payload,
    }


def _dispatch_event(request_id: str, resolved_mode: str) -> dict[str, str]:
    """Build the SSE event that reports the auto-router classification.

    Surfaced only when the request used ``auto`` mode and the router
    actually resolved it to ``question`` or ``claim``. The
    ``clarification`` outcome emits no ``stage`` because there is no
    downstream port to dispatch to.
    """
    return {
        "event": "stage",
        "data": _json_dumps(
            _event_envelope(
                "stage",
                request_id,
                {
                    "stage": "dispatch",
                    "resolved_mode": resolved_mode,
                },
            )
        ),
    }


def _json_dumps(payload: object) -> str:
    """JSON-serialise one payload deterministically."""

    import json

    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def build_envelope_stream_router(
    *,
    answer_question: AnswerQuestion,
    analyze_claim: AnalyzeClaim,
    resolve_query: ResolveQuery,
    allowed_profiles: tuple[str, ...] = (),
) -> APIRouter | None:
    """Build the streaming router; returns ``None`` if ``sse-starlette`` is missing.

    ``sse-starlette`` is the FastAPI-canonical implementation of
    Server-Sent-Events per the plan rule ("no un protocolo propio").
    If the dependency is unavailable the router is silently absent
    so the synchronous route keeps working.
    """

    try:
        from sse_starlette.sse import EventSourceResponse
    except ImportError:
        return None

    router = APIRouter(prefix="/api/v1/queries", tags=["queries"])

    async def envelope_stream_route(request: EnvelopeRequest):
        if (
            request.profile is not None
            and allowed_profiles
            and (request.profile not in allowed_profiles)
        ):
            from fastapi import HTTPException

            raise HTTPException(
                status_code=422,
                detail={"code": "unsupported_profile", "profile": request.profile},
            )
        return EventSourceResponse(
            _streaming_event_loop(
                request,
                answer_question=answer_question,
                analyze_claim=analyze_claim,
                resolve_query=resolve_query,
            )
        )

    router.add_api_route(
        "/stream",
        envelope_stream_route,
        methods=["POST"],
        name="envelope_stream",
    )
    return router
