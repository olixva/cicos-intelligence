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
    answer = subcommands.add_parser("answer")
    answer.add_argument("--text", required=True)
    answer.add_argument("--profile", choices=("baseline", "structured"), default="structured")
    answer.add_argument("--language", choices=("es", "en"), default="es")
    prepare = subcommands.add_parser("prepare-ingestion-models")
    prepare.add_argument("--output", type=Path, required=True)
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
