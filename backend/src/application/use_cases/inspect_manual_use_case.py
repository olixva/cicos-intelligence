"""Use case for reproducible source manual inspection."""

from dataclasses import dataclass
from pathlib import Path

from application.ports.outbound.source_inspector import SourceInspector
from domain.models.document import DocumentManifest, SourceIntegrityError


@dataclass(frozen=True, slots=True)
class InspectManualUseCase:
    """Verify a manual's expected identity after inspecting it."""

    inspector: SourceInspector

    def execute(self, source: Path, expected_sha256: str | None = None) -> DocumentManifest:
        """Return a manifest when the source satisfies the expected digest."""
        manifest = self.inspector.inspect(source)
        if expected_sha256 is not None and manifest.sha256 != expected_sha256:
            raise SourceIntegrityError("The source does not match the expected SHA-256")
        return manifest
