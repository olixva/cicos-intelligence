"""Command-line entry point for local source inspection."""

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from bootstrap import build_inspect_manual
from domain.models.document import SourceInspectionError, SourceIntegrityError


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="allianz")
    subcommands = parser.add_subparsers(dest="command", required=True)
    inspect_manual = subcommands.add_parser("inspect-manual")
    inspect_manual.add_argument("source", type=Path)
    inspect_manual.add_argument("--expected-sha256")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Inspect a manual and emit its manifest as JSON."""
    parser = _build_parser()
    try:
        arguments = parser.parse_args(argv)
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else 2

    if arguments.command != "inspect-manual":
        parser.error("Unknown command")

    try:
        manifest = build_inspect_manual().execute(
            arguments.source, expected_sha256=arguments.expected_sha256
        )
    except (SourceInspectionError, SourceIntegrityError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    print(json.dumps(asdict(manifest), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
