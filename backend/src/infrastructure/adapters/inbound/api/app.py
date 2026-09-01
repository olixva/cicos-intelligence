"""FastAPI application for local manual evidence and later query workflows."""

import os
from collections.abc import Callable, Mapping
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from application.ports.inbound.analyze_claim import AnalyzeClaim
from application.ports.inbound.answer_question import AnswerQuestion
from application.ports.inbound.resolve_query import ResolveQuery
from application.ports.outbound.evidence_repository import EvidenceRepository
from infrastructure.adapters.inbound.api.routes.claims import build_claim_router
from infrastructure.adapters.inbound.api.routes.manual import (
    RegisteredSource,
    build_manual_router,
    load_registered_sources,
)
from infrastructure.adapters.inbound.api.routes.queries import build_query_router
from infrastructure.adapters.inbound.api.routes.questions import build_question_router
from infrastructure.adapters.outbound.evidence_repository.filesystem_repository import (
    FilesystemEvidenceRepository,
)

_DEFAULT_EXTRACTIONS_ROOT = Path("data/extractions")
_DEFAULT_EVIDENCE_PARSER = "pypdf-6.16.2"


def create_app(
    *,
    source_catalog: Mapping[str, RegisteredSource] | None = None,
    evidence_repository: EvidenceRepository | None = None,
    active_version: str | None = None,
    required_index_ready: Callable[[], bool] | None = None,
    answer_question: AnswerQuestion | None = None,
    analyze_claim: AnalyzeClaim | None = None,
    resolve_query: ResolveQuery | None = None,
) -> FastAPI:
    """Create the API with explicit dependencies or safe local defaults."""

    if (source_catalog is None) != (evidence_repository is None):
        raise ValueError("Source catalog and evidence repository must be supplied together")
    if source_catalog is None or evidence_repository is None:
        root = Path(os.environ.get("ALLIANZ_EXTRACTIONS_ROOT", str(_DEFAULT_EXTRACTIONS_ROOT)))
        parser = os.environ.get("ALLIANZ_EVIDENCE_PARSER", _DEFAULT_EVIDENCE_PARSER)
        evidence_repository = FilesystemEvidenceRepository(root, parser)
        source_catalog = load_registered_sources(root, parser)

    catalog = dict(source_catalog)
    if active_version is None and len(catalog) == 1:
        active_version = next(iter(catalog))
    index_ready = required_index_ready or _index_not_built

    app = FastAPI(title="Allianz CICOS Claims Intelligence", version="0.1.0")

    def live() -> dict[str, str]:
        return {"status": "live"}

    def ready() -> JSONResponse:
        try:
            available = index_ready()
        except Exception:
            available = False
        if not available:
            return JSONResponse(status_code=503, content={"status": "not_ready"})
        return JSONResponse(status_code=200, content={"status": "ready"})

    app.add_api_route("/health/live", live, methods=["GET"], tags=["health"])
    app.add_api_route("/health/ready", ready, methods=["GET"], tags=["health"])
    app.include_router(
        build_manual_router(
            catalog=catalog,
            repository=evidence_repository,
            active_version=active_version,
        )
    )
    if answer_question is not None:
        app.include_router(build_question_router(answer_question))
    if analyze_claim is not None:
        app.include_router(build_claim_router(analyze_claim))
    if resolve_query is not None:
        app.include_router(build_query_router(resolve_query))
    return app


def _index_not_built() -> bool:
    """Task 7 will replace this conservative default with the required index probe."""

    return False
