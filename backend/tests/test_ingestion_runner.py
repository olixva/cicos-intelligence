from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from application.models.ingestion import IngestionJobStore
from application.services.ingestion_runner import IngestionRunner
from application.use_cases.build_retrieval_index_use_case import IndexBuildResult
from domain.models.document import DocumentManifest
from domain.models.evidence import Extraction

DOCUMENT_HASH = "b9c70c74911fad7992a01f77d861a33f10f8313c96a9f58c09b2f448a54c8344"


def _extraction() -> Extraction:
    return Extraction(
        manifest=DocumentManifest(
            document_id=f"sha256:{DOCUMENT_HASH}",
            sha256=DOCUMENT_HASH,
            filename="Manual-cide-ascide-y-cicos.pdf",
            page_count=111,
        ),
        pages=(),
        parser="pypdf-6.16.2",
        warnings=(),
    )


@dataclass
class FakeIndexer:
    calls: int = 0

    async def __call__(self, *, document_hash: str, parser: str) -> IndexBuildResult:
        self.calls += 1
        assert document_hash == DOCUMENT_HASH
        assert parser == "pypdf"
        return IndexBuildResult(collection="allianz-test", chunk_count=118)


def test_runner_reports_real_stages_and_publishes_index(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "Manual-cide-ascide-y-cicos.pdf"
    source.write_bytes(b"manual")
    monkeypatch.setattr("application.services.ingestion_runner._sha256", lambda _: DOCUMENT_HASH)
    store = IngestionJobStore(tmp_path / "job.json")
    indexer = FakeIndexer()

    def inspect_and_extract(path: Path) -> Extraction:
        assert path == source
        return _extraction()

    job = store.start()
    runner = IngestionRunner(
        store=store,
        source=source,
        expected_hash=DOCUMENT_HASH,
        inspect_and_extract=inspect_and_extract,
        publish_index=indexer,
    )

    import asyncio

    asyncio.run(runner.run(job.job_id))
    result = store.load().last_job
    assert result is not None
    assert result.status == "succeeded"
    assert result.pages == 111
    assert result.chunks == 118
    assert [event.stage for event in result.events] == [
        "verifying_manual",
        "extracting_evidence",
        "publishing_index",
        "published_index",
    ]
    assert indexer.calls == 1


def test_runner_rejects_an_unexpected_manual_hash_without_indexing(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "manual.pdf"
    source.write_bytes(b"not-the-manual")
    monkeypatch.setattr("application.services.ingestion_runner._sha256", lambda _: DOCUMENT_HASH)
    store = IngestionJobStore(tmp_path / "job.json")
    indexer = FakeIndexer()

    def inspect_and_extract(path: Path) -> Extraction:
        return Extraction(
            manifest=DocumentManifest("sha256:wrong", "0" * 64, path.name, 1),
            pages=(),
            parser="pypdf-6.16.2",
            warnings=(),
        )

    job = store.start()
    runner = IngestionRunner(
        store=store,
        source=source,
        expected_hash=DOCUMENT_HASH,
        inspect_and_extract=inspect_and_extract,
        publish_index=indexer,
    )

    import asyncio

    asyncio.run(runner.run(job.job_id))
    result = store.load().last_job
    assert result is not None
    assert result.status == "failed"
    assert result.error == "El manual no coincide con la fuente verificada."
    assert indexer.calls == 0
