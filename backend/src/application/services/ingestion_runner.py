"""Orchestrate the verified manual ingestion without invoking the CLI."""

from __future__ import annotations

import hashlib
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from application.models.ingestion import (
    IngestionEvent,
    IngestionJobStore,
    IngestionStage,
    IngestionStatus,
)
from application.use_cases.build_retrieval_index_use_case import IndexBuildResult
from domain.models.evidence import Extraction

ExtractManual = Callable[[Path], Extraction]
PublishIndex = Callable[..., Awaitable[IndexBuildResult]]
_LOGGER = logging.getLogger(__name__)


class IngestionRunner:
    """Run the two existing use cases and expose only safe progress metadata."""

    def __init__(
        self,
        *,
        store: IngestionJobStore,
        source: Path,
        expected_hash: str,
        inspect_and_extract: ExtractManual,
        publish_index: PublishIndex,
    ) -> None:
        self._store = store
        self._source = source
        self._expected_hash = expected_hash
        self._inspect_and_extract = inspect_and_extract
        self._publish_index = publish_index

    async def run(self, job_id: str) -> None:
        try:
            self._event(job_id, "verifying_manual", "running")
            actual_hash = _sha256(self._source)
            if actual_hash != self._expected_hash:
                raise _UnsafeManual()

            extraction = self._inspect_and_extract(self._source)
            if extraction.manifest.sha256 != self._expected_hash:
                raise _UnsafeManual()
            self._store.update(
                job_id,
                document_hash=extraction.manifest.sha256,
                parser=extraction.parser,
            )
            self._event(
                job_id,
                "extracting_evidence",
                "running",
                pages=extraction.manifest.page_count,
            )

            self._event(job_id, "publishing_index", "running")
            index = await self._publish_index(
                document_hash=extraction.manifest.sha256,
                parser="pypdf",
            )
            self._event(
                job_id,
                "published_index",
                "succeeded",
                collection=index.collection,
                chunks=index.chunk_count,
            )
            self._store.update(
                job_id,
                status="succeeded",
                stage="published_index",
                finished_at=datetime.now(UTC),
                pages=extraction.manifest.page_count,
                chunks=index.chunk_count,
                collection=index.collection,
            )
        except _UnsafeManual:
            self._fail(job_id, "El manual no coincide con la fuente verificada.")
        except Exception:
            _LOGGER.exception("Administrative ingestion failed for job %s", job_id)
            self._fail(job_id, "La ingesta no se pudo completar. El índice anterior sigue activo.")

    def _event(
        self,
        job_id: str,
        stage: str,
        status: str,
        **data: str | int | None,
    ) -> None:
        self._store.append_event(
            job_id,
            IngestionEvent(
                event_id=str(uuid.uuid4()),
                job_id=job_id,
                timestamp=datetime.now(UTC),
                stage=cast(IngestionStage, stage),
                status=cast(IngestionStatus, status),
                data=data,
            ),
        )

    def _fail(self, job_id: str, message: str) -> None:
        self._store.update(
            job_id,
            status="failed",
            finished_at=datetime.now(UTC),
            error=message,
        )


class _UnsafeManual(Exception):
    """Internal sentinel for a source identity mismatch."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
