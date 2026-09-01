"""Application composition root."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

from application.ports.inbound.answer_question import AnswerQuestion
from application.ports.inbound.ingest_document import IngestDocument
from application.ports.inbound.inspect_manual import InspectManual
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
            evidence_repository=FilesystemEvidenceRepository(evidence_root, parser),
            publisher=publisher,
            profile=profile,
        ).execute(document_hash=document_hash, resolved_parser=parser)
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


def build_api() -> FastAPI:
    """Build the local HTTP adapter through its dependency-aware factory."""

    from infrastructure.adapters.inbound.api.app import create_app

    return create_app()
