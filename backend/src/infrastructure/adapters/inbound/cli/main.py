"""Command-line entry point for local source inspection."""

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path

from bootstrap import build_ingest_document, build_inspect_manual
from domain.models.document import SourceInspectionError, SourceIntegrityError
from domain.models.evidence import Extraction
from infrastructure.adapters.outbound.evidence_repository.filesystem_repository import (
    EvidencePublicationError,
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
        SourceInspectionError,
        SourceIntegrityError,
        ValueError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    payload = _extraction_metadata(result) if isinstance(result, Extraction) else asdict(result)
    print(json.dumps(payload, sort_keys=True))
    return 0


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
