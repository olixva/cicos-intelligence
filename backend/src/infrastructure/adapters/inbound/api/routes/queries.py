"""Auto-router HTTP endpoint backed by the closed-enum LangGraph selector.

The route is mounted only when a ``ResolveQuery`` port is injected into
``create_app``. The response shape is intentionally minimal: the caller
receives the selected ``decision`` plus a short ``rationale`` and trace
identifier. The full dispatch payload (``QueryExecution`` /
``ClaimExecution`` / ``ClarificationResult``) is fetched by following the
explicit question or claim endpoint, or by inspecting the clarification
``message`` field on the auto branch.
"""

from __future__ import annotations

from fastapi import APIRouter

from application.models.query import QueryInput
from application.ports.inbound.resolve_query import ResolveQuery
from infrastructure.adapters.inbound.api.schemas.query import (
    QueryResolveRequest,
    QueryResolveResponse,
)


def build_query_router(resolve_query: ResolveQuery) -> APIRouter:
    """Bind the resolve route solely to the closed-enum auto router port."""

    router = APIRouter(prefix="/api/v1/queries", tags=["queries"])

    async def resolve_query_route(request: QueryResolveRequest) -> QueryResolveResponse:
        execution = await resolve_query.execute(
            QueryInput(text=request.text, language=request.language)
        )
        return QueryResolveResponse.from_domain(execution)

    router.add_api_route(
        "/resolve",
        resolve_query_route,
        methods=["POST"],
        response_model=QueryResolveResponse,
    )
    return router