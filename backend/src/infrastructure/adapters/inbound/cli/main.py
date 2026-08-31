"""Command-line entry point for local source inspection."""

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from bootstrap import build_ingest_document, build_inspect_manual
from domain.models.document import SourceInspectionError, SourceIntegrityError
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
    ingest.add_argument("--parser", choices=("pypdf",), required=True)
    ingest.add_argument("--output", type=Path, required=True)
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

    print(json.dumps(asdict(result), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
