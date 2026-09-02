"""Application composition root."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, cast

from application.ports.inbound.analyze_claim import AnalyzeClaim
from application.ports.inbound.answer_question import AnswerQuestion
from application.ports.inbound.ingest_document import IngestDocument
from application.ports.inbound.inspect_manual import InspectManual
from application.ports.inbound.resolve_query import ResolveQuery
from application.use_cases.analyze_claim_use_case import AnalyzeClaimUseCase
from application.use_cases.answer_question_use_case import AnswerQuestionUseCase
from application.use_cases.build_retrieval_index_use_case import (
    BuildRetrievalIndexUseCase,
    IndexBuildResult,
)
from application.use_cases.ingest_document_use_case import IngestDocumentUseCase
from application.use_cases.inspect_manual_use_case import InspectManualUseCase
from infrastructure.adapters.outbound.document_parser.pypdf_parser import PypdfDocumentParser
from infrastructure.adapters.outbound.evidence_repository.filesystem_repository import (
    FilesystemEvidenceRepository,
)
from infrastructure.adapters.outbound.source_inspector.pypdf_source_inspector import (
    PypdfSourceInspector,
)

if TYPE_CHECKING:
    from fastapi import FastAPI
    from langfuse.experiment import EvaluatorFunction, ExperimentResult

_SKIPPED_PORT_LOGGER = logging.getLogger(__name__)


def build_inspect_manual() -> InspectManual:
    """Build the manual-inspection use case with its PDF adapter."""
    return InspectManualUseCase(inspector=PypdfSourceInspector())


def build_ingest_document(output: Path, parser: str = "pypdf") -> IngestDocument:
    """Build an explicit parser without loading optional ingestion dependencies by default."""
    if parser == "pypdf":
        document_parser = PypdfDocumentParser()
    elif parser == "docling":
        from infrastructure.adapters.outbound.document_parser.docling_parser import DoclingParser

        document_parser = DoclingParser()
    else:
        raise ValueError(f"Unsupported parser: {parser}")
    return IngestDocumentUseCase(
        parser=document_parser,
        repository=FilesystemEvidenceRepository(output, document_parser.parser),
    )


async def build_and_publish_retrieval_index(
    *,
    document_hash: str,
    evidence_root: Path,
    parser: str,
    profile_name: str,
    qdrant_url: str,
) -> IndexBuildResult:
    """Compose the local Qdrant and OpenAI adapters for a verified index publication."""
    from qdrant_client import AsyncQdrantClient

    from infrastructure.adapters.outbound.embedding_provider.openai_embedding_provider import (
        OpenAIEmbeddingProvider,
    )
    from infrastructure.adapters.outbound.retriever.index_builder import QdrantIndexBuilder
    from infrastructure.adapters.outbound.retriever.qdrant_retriever import FastEmbedBm25Encoder
    from infrastructure.config.profiles import load_profile

    profile = load_profile(profile_name, profile_catalog_dir())
    # The CLI passes only the parser family name (e.g. ``pypdf``); the
    # filesystem layer requires the fully versioned directory name (e.g.
    # ``pypdf-6.16.2``). Resolve the version here so callers do not
    # have to thread the version through.
    resolved_parser = _resolve_published_parser(evidence_root, document_hash, parser)
    client = AsyncQdrantClient(url=qdrant_url)
    try:
        publisher = QdrantIndexBuilder(
            client=client,
            embedding_provider=OpenAIEmbeddingProvider(
                model=profile.embedding_model,
                dimensions=profile.dimensions,
            ),
            sparse_encoder=FastEmbedBm25Encoder(language=profile.lexical_language),
            active_alias="allianz-manual-active",
        )
        return await BuildRetrievalIndexUseCase(
            evidence_repository=FilesystemEvidenceRepository(evidence_root, resolved_parser),
            publisher=publisher,
            profile=profile,
        ).execute(document_hash=document_hash, resolved_parser=resolved_parser)
    finally:
        await client.close()


def profile_catalog_dir() -> Path:
    """Locate the project-owned strict profile catalog outside importable source modules."""
    return Path(__file__).parent.parent / "configs"


def build_answer_question(profile_name: str) -> AnswerQuestion:
    """Compose the local question flow against the active Qdrant index and pinned prompt."""
    import os

    from langchain_core.callbacks import BaseCallbackHandler
    from langfuse import Langfuse
    from langfuse.langchain import CallbackHandler
    from qdrant_client import AsyncQdrantClient

    from infrastructure.adapters.outbound.embedding_provider.openai_embedding_provider import (
        OpenAIEmbeddingProvider,
    )
    from infrastructure.adapters.outbound.language_model.openai_language_model import (
        LangfusePromptClient,
        OpenAILanguageModel,
        load_langfuse_prompt,
    )
    from infrastructure.adapters.outbound.question_workflow.langgraph_workflow import (
        LangGraphQuestionWorkflow,
    )
    from infrastructure.adapters.outbound.retriever.qdrant_retriever import (
        FastEmbedBm25Encoder,
        QdrantRetriever,
    )
    from infrastructure.config.profiles import load_profile

    profile = load_profile(profile_name, profile_catalog_dir())
    _require_local_langfuse_environment()
    document_hash = os.environ.get(
        "ALLIANZ_DOCUMENT_HASH",
        "b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344",
    )
    evidence_root = Path(os.environ.get("ALLIANZ_EVIDENCE_ROOT", "data/extractions"))
    parser = _resolve_published_parser(evidence_root, document_hash, profile.parser)
    signature = profile.build_index_signature(document_hash, parser)
    langfuse = Langfuse()
    prompt = load_langfuse_prompt(
        cast(LangfusePromptClient, langfuse),
        name=os.environ.get("ALLIANZ_QUESTION_PROMPT_NAME", "document-question"),
        version=_positive_environment_integer("ALLIANZ_QUESTION_PROMPT_VERSION", 1),
    )
    retriever = QdrantRetriever(
        client=AsyncQdrantClient(url=os.environ.get("QDRANT_URL", "http://127.0.0.1:6333")),
        embedding_provider=OpenAIEmbeddingProvider(
            model=profile.embedding_model, dimensions=profile.dimensions
        ),
        sparse_encoder=FastEmbedBm25Encoder(language=profile.lexical_language),
        collection="allianz-manual-active",
        expected_signature=signature,
    )

    def callback_factory(trace_id: str) -> BaseCallbackHandler:
        return CallbackHandler(trace_context={"trace_id": trace_id})

    return AnswerQuestionUseCase(
        LangGraphQuestionWorkflow(
            retriever=retriever,
            evidence_repository=FilesystemEvidenceRepository(evidence_root, parser),
            language_model=OpenAILanguageModel(
                model=os.environ.get("OPENAI_ANSWER_MODEL", "gpt-5.4"), prompt=prompt
            ),
            trace_id_factory=langfuse.create_trace_id,
            callback_factory=callback_factory,
            trace_url_factory=lambda trace_id: langfuse.get_trace_url(trace_id=trace_id),
        )
    )


def build_analyze_claim(profile_name: str) -> AnalyzeClaim:
    """Compose the source-grounded claim flow with the same active local index as questions."""
    import os

    from langchain_core.callbacks import BaseCallbackHandler
    from langfuse import Langfuse
    from langfuse.langchain import CallbackHandler
    from qdrant_client import AsyncQdrantClient

    from infrastructure.adapters.outbound.claim_workflow.langgraph_workflow import (
        LangGraphClaimWorkflow,
    )
    from infrastructure.adapters.outbound.embedding_provider.openai_embedding_provider import (
        OpenAIEmbeddingProvider,
    )
    from infrastructure.adapters.outbound.language_model.openai_claim_fact_extractor import (
        OpenAIClaimFactExtractor,
    )
    from infrastructure.adapters.outbound.retriever.qdrant_retriever import (
        FastEmbedBm25Encoder,
        QdrantRetriever,
    )
    from infrastructure.config.profiles import load_profile

    profile = load_profile(profile_name, profile_catalog_dir())
    _require_local_langfuse_environment()
    document_hash = os.environ.get(
        "ALLIANZ_DOCUMENT_HASH",
        "b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344",
    )
    evidence_root = Path(os.environ.get("ALLIANZ_EVIDENCE_ROOT", "data/extractions"))
    parser = _resolve_published_parser(evidence_root, document_hash, profile.parser)
    signature = profile.build_index_signature(document_hash, parser)

    def callback_factory(trace_id: str) -> BaseCallbackHandler:
        return CallbackHandler(trace_context={"trace_id": trace_id})

    return AnalyzeClaimUseCase(
        LangGraphClaimWorkflow(
            fact_extractor=OpenAIClaimFactExtractor(
                model=os.environ.get("OPENAI_CLAIM_EXTRACTION_MODEL", "gpt-4.1-mini")
            ),
            retriever=QdrantRetriever(
                client=AsyncQdrantClient(url=os.environ.get("QDRANT_URL", "http://127.0.0.1:6333")),
                embedding_provider=OpenAIEmbeddingProvider(
                    model=profile.embedding_model, dimensions=profile.dimensions
                ),
                sparse_encoder=FastEmbedBm25Encoder(language=profile.lexical_language),
                collection="allianz-manual-active",
                expected_signature=signature,
            ),
            evidence_repository=FilesystemEvidenceRepository(evidence_root, parser),
            trace_id_factory=Langfuse().create_trace_id,
            callback_factory=callback_factory,
            trace_url_factory=lambda trace_id: Langfuse().get_trace_url(trace_id=trace_id),
        )
    )


def _resolve_published_parser(root: Path, document_hash: str, parser: str) -> str:
    publication = root / document_hash
    try:
        matches = tuple(
            path.name
            for path in publication.iterdir()
            if path.is_dir() and path.name.startswith(f"{parser}-")
        )
    except OSError as error:
        raise ValueError("evidence publication is unavailable") from error
    if len(matches) != 1:
        raise ValueError(f"expected one published {parser} parser, found {len(matches)}")
    return matches[0]


def _positive_environment_integer(name: str, default: int) -> int:
    import os

    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError as error:
        raise ValueError(f"{name} must be a positive integer") from error
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _require_local_langfuse_environment() -> None:
    import os

    required = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_BASE_URL")
    missing = tuple(name for name in required if not os.environ.get(name, "").strip())
    if missing:
        raise ValueError(f"missing Langfuse configuration: {', '.join(missing)}")
    if os.environ["LANGFUSE_BASE_URL"] != "http://127.0.0.1:3000":
        raise ValueError("LANGFUSE_BASE_URL must be http://127.0.0.1:3000 for local execution")


def build_api(
    *,
    profile_name: str | None = None,
    question_profile: str | None = None,
    claim_profile: str | None = None,
    resolve_query_profile: str | None = None,
    required_index_ready: Callable[[], bool] | None = None,
) -> FastAPI:
    """Build the local HTTP adapter through its dependency-aware factory.

    The question, claim, and resolve routers are wired only when their
    respective factories succeed. When ``profile_name`` is provided it
    acts as the default for all three routers; ``question_profile``,
    ``claim_profile``, and ``resolve_query_profile`` override it on a
    per-router basis. A configuration that builds no router at all is
    treated as a hard failure so the operator is not silently served an
    empty API.

    ``required_index_ready`` is forwarded to ``create_app`` so the
    ``/health/ready`` endpoint reports the real index status. When
    ``None`` (default), the production safe-default of "not built" is
    used; local entry points such as ``asgi_local`` pass a probe that
    checks the Qdrant active alias.
    """

    from infrastructure.adapters.inbound.api.app import create_app

    answer_question = _try_build_answer_question(question_profile or profile_name)
    analyze_claim = _try_build_analyze_claim(claim_profile or profile_name)
    resolve_query = _try_build_resolve_query(resolve_query_profile or profile_name)
    if answer_question is None and analyze_claim is None and resolve_query is None:
        raise RuntimeError(
            "build_api() could not compose any workflow port; "
            "pass profile_name or any of question_profile/claim_profile/resolve_query_profile, "
            "or fix the Langfuse/Qdrant configuration before serving the API"
        )
    return create_app(
        answer_question=answer_question,
        analyze_claim=analyze_claim,
        resolve_query=resolve_query,
        allowed_profiles=_known_profiles(),
        required_index_ready=required_index_ready,
    )


def _known_profiles() -> tuple[str, ...]:
    """Catalog of profile names the envelope accepts.

    Phase 4 v1: the envelope validates the ``profile`` body field for
    shape only; per-request profile override is not yet honored at
    runtime. Mismatches return 422 with ``code=unsupported_profile``.
    Profiles are read from the YAML catalog directory when present.
    """

    catalog = profile_catalog_dir()
    if not catalog.exists():
        return ()
    return tuple(
        path.stem
        for path in sorted(catalog.glob("*.yaml"))
        if path.is_file() and path.stem not in {"__pycache__"}
    )


def _try_build_answer_question(profile: str | None) -> AnswerQuestion | None:
    if profile is None:
        return None
    try:
        return build_answer_question(profile)
    except (ValueError, OSError) as error:
        return _log_skipped_port("answer_question", profile, error)


def _try_build_analyze_claim(profile: str | None) -> AnalyzeClaim | None:
    if profile is None:
        return None
    try:
        return build_analyze_claim(profile)
    except (ValueError, OSError) as error:
        return _log_skipped_port("analyze_claim", profile, error)


def _try_build_resolve_query(profile: str | None) -> ResolveQuery | None:
    if profile is None:
        return None
    try:
        return build_resolve_query(profile)
    except (ValueError, OSError) as error:
        return _log_skipped_port("resolve_query", profile, error)


def _log_skipped_port(port_name: str, profile: str, error: Exception) -> None:
    """Surface a single informative line when a workflow port cannot be built.

    The adapter intentionally continues so other ports can still mount; only
    when every port fails does ``build_api`` raise.
    """

    _SKIPPED_PORT_LOGGER.warning(
        "build_api: skipping %s port for profile %r: %s", port_name, profile, error
    )
    return None


def build_resolve_query(profile_name: str) -> ResolveQuery:
    """Compose the closed-enum auto router against the same active index as questions and claims.

    The classifier is backed by its own ``OpenAIRoutingLanguageModel``
    instance loaded with the dedicated ``auto-router`` prompt version
    (configurable via ``ALLIANZ_ROUTER_PROMPT_VERSION``); it uses a
    separate structured output schema (``RouteDecisionSchema``) so the
    model can emit any of the three closed-enum routes. The dispatch
    graph reuses the existing question and claim factories so
    retrieval, evidence, and Langfuse traces stay consistent across
    modes.
    """

    import os

    from langchain_core.callbacks import BaseCallbackHandler
    from langfuse import Langfuse
    from langfuse.langchain import CallbackHandler

    from infrastructure.adapters.outbound.language_model.openai_language_model import (
        LangfuseTextPrompt,
    )
    from infrastructure.adapters.outbound.language_model.openai_routing_language_model import (
        OpenAIRoutingLanguageModel,
        RoutingPrompt,
    )
    from infrastructure.adapters.outbound.query_workflow.langgraph_workflow import (
        build_resolve_query_workflow,
    )

    _require_local_langfuse_environment()
    langfuse = Langfuse()
    prompt_name = os.environ.get("ALLIANZ_ROUTER_PROMPT_NAME", "auto-router")
    prompt_version = _positive_environment_integer("ALLIANZ_ROUTER_PROMPT_VERSION", 1)
    prompt_text = cast(
        LangfuseTextPrompt,
        langfuse.get_prompt(prompt_name, version=prompt_version, type="text"),
    ).prompt
    classifier = OpenAIRoutingLanguageModel(
        model=os.environ.get("ALLIANZ_ROUTER_MODEL", "gpt-5.4"),
        prompt=RoutingPrompt(name=prompt_name, version=prompt_version, content=prompt_text),
    )
    answer_question = build_answer_question(profile_name)
    analyze_claim = build_analyze_claim(profile_name)

    def callback_factory(trace_id: str) -> BaseCallbackHandler:
        return CallbackHandler(trace_context={"trace_id": trace_id})

    return build_resolve_query_workflow(
        classifier=classifier,
        answer_question=answer_question,
        analyze_claim=analyze_claim,
        callback_factory=callback_factory,
    )


def build_question_experiment_runner(profile_name: str) -> Callable[..., ExperimentResult]:
    """Return a closure that runs native Langfuse question experiments.

    The closure injects the live ``Langfuse`` client into
    ``run_question_experiment`` so tests can substitute fakes without
    monkeypatching module globals.
    """

    from langfuse import Langfuse

    from infrastructure.adapters.outbound.evaluation.langfuse_experiments import (
        run_question_experiment,
    )

    _require_local_langfuse_environment()
    client = Langfuse()

    def runner(
        dataset_name: str,
        dataset_version: str,
        evaluators: Sequence[EvaluatorFunction],
    ) -> ExperimentResult:
        return run_question_experiment(
            profile_name=profile_name,
            dataset_name=dataset_name,
            dataset_version=dataset_version,
            evaluators=evaluators,
            langfuse_client=client,
        )

    return runner
