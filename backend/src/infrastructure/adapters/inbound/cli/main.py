"""Command-line entry point for local source inspection."""

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path

from application.models.query import QueryExecution, QueryInput
from application.ports.outbound.language_model import LanguageModelError
from bootstrap import (
    build_and_publish_retrieval_index,
    build_answer_question,
    build_ingest_document,
    build_inspect_manual,
)
from domain.models.document import SourceInspectionError, SourceIntegrityError
from domain.models.evidence import Extraction
from infrastructure.adapters.outbound.evidence_repository.filesystem_repository import (
    EvidencePublicationError,
)
from infrastructure.adapters.outbound.question_workflow.langgraph_workflow import (
    QuestionWorkflowTimeoutError,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="allianz")
    subcommands = parser.add_subparsers(dest="command", required=True)
    inspect_manual = subcommands.add_parser("inspect-manual")
    inspect_manual.add_argument("source", type=Path)
    inspect_manual.add_argument("--expected-sha256")
    ingest = subcommands.add_parser("ingest")
    ingest.add_argument("source", type=Path)
    ingest.add_argument("--parser", choices=("pypdf", "docling"), required=True)
    ingest.add_argument("--output", type=Path, required=True)
    index = subcommands.add_parser("index")
    index.add_argument("--document-hash", required=True)
    index.add_argument("--parser", required=True)
    index.add_argument("--evidence-root", type=Path, required=True)
    index.add_argument("--profile", choices=("baseline", "structured"), default="structured")
    index.add_argument("--qdrant-url", default="http://127.0.0.1:6333")
    rollback = subcommands.add_parser("index-rollback")
    rollback.add_argument("--collection", required=True)
    rollback.add_argument("--qdrant-url", default="http://127.0.0.1:6333")
    list_collections = subcommands.add_parser("list-index-versions")
    list_collections.add_argument("--qdrant-url", default="http://127.0.0.1:6333")
    answer = subcommands.add_parser("answer")
    answer.add_argument("--text", required=True)
    answer.add_argument("--profile", choices=("baseline", "structured"), default="structured")
    answer.add_argument("--language", choices=("es", "en"), default="es")
    prepare = subcommands.add_parser("prepare-ingestion-models")
    prepare.add_argument("--output", type=Path, required=True)
    compare_parsers = subcommands.add_parser("compare-parsers")
    compare_parsers.add_argument("source", type=Path)
    compare_parsers.add_argument("--output", type=Path, required=True)
    doctor = subcommands.add_parser("doctor")
    doctor.add_argument(
        "--operation",
        choices=("services", "containers", "retrieval", "evaluation", "generation", "all"),
        default="services",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Inspect a manual and emit its manifest as JSON."""
    parser = _build_parser()
    try:
        arguments = parser.parse_args(argv)
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else 2

    try:
        if arguments.command == "inspect-manual":
            result = build_inspect_manual().execute(
                arguments.source, expected_sha256=arguments.expected_sha256
            )
        elif arguments.command == "ingest":
            result = build_ingest_document(arguments.output, arguments.parser).execute(
                arguments.source
            )
        elif arguments.command == "index":
            result = asyncio.run(
                build_and_publish_retrieval_index(
                    document_hash=arguments.document_hash,
                    evidence_root=arguments.evidence_root,
                    parser=arguments.parser,
                    profile_name=arguments.profile,
                    qdrant_url=arguments.qdrant_url,
                )
            )
            print(
                json.dumps(
                    {"collection": result.collection, "chunk_count": result.chunk_count},
                    sort_keys=True,
                )
            )
            return 0
        elif arguments.command == "index-rollback":
            return _run_index_rollback(arguments)
        elif arguments.command == "list-index-versions":
            return _run_list_index_versions(arguments)
        elif arguments.command == "answer":
            execution = asyncio.run(
                build_answer_question(arguments.profile).execute(
                    QueryInput(arguments.text, arguments.language)
                )
            )
            print(
                json.dumps(_query_execution_payload(execution), ensure_ascii=False, sort_keys=True)
            )
            return 0
        elif arguments.command == "prepare-ingestion-models":
            from infrastructure.adapters.outbound.document_parser.model_artifacts import (
                prepare_model_bundle,
            )

            bundle = prepare_model_bundle(arguments.output)
            print(
                json.dumps(
                    {
                        "bundle_sha256": bundle.digest,
                        "files": len(bundle.manifest.files),
                        "output": str(bundle.root),
                    },
                    sort_keys=True,
                )
            )
            return 0
        elif arguments.command == "compare-parsers":
            return _run_parser_comparison(arguments)
        elif arguments.command == "doctor":
            from infrastructure.adapters.inbound.cli import doctor

            status = doctor.check_environment(operation=arguments.operation)
            print(json.dumps(status, sort_keys=True))
            return 0 if status["ready"] is True else 1
        else:
            parser.error("Unknown command")
    except (
        EvidencePublicationError,
        LanguageModelError,
        QuestionWorkflowTimeoutError,
        SourceInspectionError,
        SourceIntegrityError,
        ValueError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    payload = _extraction_metadata(result) if isinstance(result, Extraction) else asdict(result)
    print(json.dumps(payload, sort_keys=True))
    return 0


def _run_index_rollback(arguments: argparse.Namespace) -> int:
    """Switch the active alias back to a previously published collection."""
    import asyncio

    from infrastructure.adapters.outbound.retriever.index_builder import (
        AmbiguousIndexPublicationError,
        IndexPublicationError,
        QdrantIndexBuilder,
    )
    from qdrant_client import AsyncQdrantClient

    async def _run() -> dict[str, object]:
        client = AsyncQdrantClient(url=arguments.qdrant_url)
        try:
            builder = QdrantIndexBuilder(
                client=client,
                embedding_provider=_embedding_double(),
                sparse_encoder=_sparse_double(),
                active_alias="allianz-manual-active",
            )
            await builder.rollback_alias(arguments.collection)
            active = await builder._active_collection()
            return {"collection": arguments.collection, "active_alias": active}
        finally:
            await client.close()

    try:
        payload = asyncio.run(_run())
    except (IndexPublicationError, AmbiguousIndexPublicationError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(json.dumps(payload, sort_keys=True))
    return 0


def _run_list_index_versions(arguments: argparse.Namespace) -> int:
    """List every Qdrant collection in the project namespace with its signature digest."""
    import asyncio

    from qdrant_client import AsyncQdrantClient

    from application.models.retrieval import IndexSignature
    from infrastructure.adapters.outbound.retriever.qdrant_retriever import (
        InvalidIndexDataError,
        signature_from_metadata,
    )

    async def _run() -> list[dict[str, object]]:
        client = AsyncQdrantClient(url=arguments.qdrant_url)
        try:
            collections = await client.get_collections()
            rows: list[dict[str, object]] = []
            for entry in collections.collections:
                info = await client.get_collection(entry.name)
                try:
                    signature = signature_from_metadata(info.config.metadata)
                    signature_dict = {
                        field.name: getattr(signature, field.name)
                        for field in _fields()
                    }
                except InvalidIndexDataError:
                    signature_dict = None
                rows.append({"collection": entry.name, "index_signature": signature_dict})
            aliases = await client.get_aliases()
            active = {
                alias.alias_name: alias.collection_name
                for alias in aliases.aliases
                if alias.alias_name == "allianz-manual-active"
            }
            return [{"active_alias": active.get("allianz-manual-active"), "versions": rows}]
        finally:
            await client.close()

    def _fields():
        from dataclasses import fields

        return fields(IndexSignature)

    try:
        payload = asyncio.run(_run())
    except Exception as error:  # noqa: BLE001
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(json.dumps(payload, sort_keys=True, indent=2, default=str))
    return 0


def _embedding_double():  # type: ignore[no-untyped-def]
    from application.ports.outbound.embedding_provider import EmbeddingProvider

    class _Double(EmbeddingProvider):
        async def embed(self, texts):  # type: ignore[no-untyped-def]
            return tuple(tuple() for _ in texts)

    return _Double()


def _sparse_double():  # type: ignore[no-untyped-def]
    from infrastructure.adapters.outbound.retriever.qdrant_retriever import SparseEncoder

    class _Double(SparseEncoder):
        async def embed_documents(self, texts):  # type: ignore[no-untyped-def]
            return tuple()

        async def embed_query(self, text):  # type: ignore[no-untyped-def]
            from qdrant_client import models

            return models.SparseVector(indices=[], values=[])

    return _Double()


def _run_parser_comparison(arguments: argparse.Namespace) -> int:
    """Run both parsers over the source and emit a JSON comparison report."""
    import time

    from infrastructure.adapters.outbound.document_parser.pypdf_parser import (
        PypdfDocumentParser,
    )

    output_root: Path = arguments.output
    output_root.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    pypdf_extraction = PypdfDocumentParser().parse(arguments.source)
    pypdf_elapsed = time.perf_counter() - started

    started = time.perf_counter()
    from infrastructure.adapters.outbound.document_parser.docling_parser import (
        DoclingParser,
    )

    docling_extraction = DoclingParser().parse(arguments.source)
    docling_elapsed = time.perf_counter() - started

    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[5] / "scripts"))
    from compare_parsers import compare_extractions  # type: ignore[import-not-found]

    report = compare_extractions(pypdf_extraction, docling_extraction)
    report["timings_seconds"] = {
        "pypdf": pypdf_elapsed,
        "docling": docling_elapsed,
    }
    report["bytes"] = {
        "pypdf": sum(len(asset.data) for asset in pypdf_extraction.assets),
        "docling": sum(len(asset.data) for asset in docling_extraction.assets),
    }
    report_path = output_root / f"{pypdf_extraction.manifest.sha256}.comparison.json"
    report_path.write_text(
        json.dumps(report, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({"report": str(report_path), **report}, sort_keys=True, ensure_ascii=False))
    return 0


def _query_execution_payload(execution: QueryExecution) -> dict[str, object]:
    """Serialize grounded output and effective context without internal state or credentials."""
    return {
        "status": execution.result.status,
        "blocks": [
            {"text": block.text, "evidence_ids": list(block.evidence_ids)}
            for block in execution.result.blocks
        ],
        "context": [
            {
                "evidence_ids": list(item.evidence_ids),
                "text": item.text,
                "delivery": item.delivery,
                "sources": [
                    {
                        "evidence_id": source.evidence_id,
                        "pdf_page": source.pdf_page,
                        "printed_label": source.printed_label,
                        "image_path": source.image_path,
                    }
                    for source in item.sources
                ],
            }
            for item in execution.context
        ],
        "trace_id": execution.trace_id,
    }


def _extraction_metadata(extraction: Extraction) -> dict[str, object]:
    """Return CLI-safe publication metadata without copying source or rendered bytes."""
    return {
        **asdict(extraction.manifest),
        "parser": extraction.parser,
        "warnings": list(extraction.warnings),
        "assets": [
            {
                "path": asset.path,
                "sha256": sha256(asset.data).hexdigest(),
                "size": len(asset.data),
            }
            for asset in extraction.assets
        ],
    }


if __name__ == "__main__":
    raise SystemExit(main())
