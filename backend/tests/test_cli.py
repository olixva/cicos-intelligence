from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.base_models import ConversionStatus, InputFormat
from docling.datamodel.document import ConversionResult, InputDocument
from docling.document_converter import DocumentConverter
from docling_core.types.doc.base import Size
from docling_core.types.doc.document import DoclingDocument
from pypdf import PdfWriter
from pytest import CaptureFixture

from infrastructure.adapters.outbound.document_parser.model_artifacts import ModelBundle


def test_inspect_manual_prints_a_json_manifest(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    """A valid source must return its manifest as JSON on standard output."""
    from infrastructure.adapters.inbound.cli.main import main

    source = tmp_path / "manual.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(str(source))
    expected_hash = sha256(source.read_bytes()).hexdigest()

    result = main(["inspect-manual", str(source), "--expected-sha256", expected_hash])

    captured = capsys.readouterr()
    assert result == 0
    assert json.loads(captured.out) == {
        "document_id": f"sha256:{expected_hash}",
        "filename": "manual.pdf",
        "page_count": 1,
        "sha256": expected_hash,
    }
    assert captured.err == ""


def test_inspect_manual_reports_input_errors_without_a_traceback(
    capsys: CaptureFixture[str], tmp_path: Path
) -> None:
    """An unreadable input must be a concise CLI error with status 2."""
    from infrastructure.adapters.inbound.cli.main import main

    result = main(["inspect-manual", str(tmp_path / "missing.pdf")])

    captured = capsys.readouterr()
    assert result == 2
    assert captured.out == ""
    assert "Unable to read source" in captured.err
    assert "Traceback" not in captured.err


def test_ingest_docling_prints_metadata_without_binary_assets(
    capsys: CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fake_model_bundle: ModelBundle,
) -> None:
    """Serializing a structured extraction must never send original or PNG bytes to stdout."""
    from io import BytesIO

    from infrastructure.adapters.inbound.cli.main import main

    source = tmp_path / "manual.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=100)
    writer.write(source)
    original = source.read_bytes()
    document = DoclingDocument(name="manual")
    document.add_page(1, Size(width=200, height=100))
    converted = ConversionResult(
        input=InputDocument(
            path_or_stream=BytesIO(original),
            format=InputFormat.PDF,
            backend=PyPdfiumDocumentBackend,
            filename=source.name,
        ),
        document=document,
        status=ConversionStatus.SUCCESS,
    )

    def convert(*args: Any, **kwargs: Any) -> ConversionResult:
        return converted

    monkeypatch.setattr(DocumentConverter, "convert", convert)
    monkeypatch.setattr(
        "infrastructure.adapters.outbound.document_parser.docling_parser.default_model_bundle",
        lambda: fake_model_bundle,
    )

    result = main(
        [
            "ingest",
            str(source),
            "--parser",
            "docling",
            "--output",
            str(tmp_path / "evidence"),
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert result == 0
    assert captured.err == ""
    assert payload["document_id"] == f"sha256:{sha256(original).hexdigest()}"
    assert payload["page_count"] == 1
    assert payload["parser"].startswith("docling-2.124.0-pdfium-5.13.0-")
    assert {asset["path"] for asset in payload["assets"]} >= {
        "original.pdf",
        "pages/1.png",
        "document.json",
        "document.md",
        "diagnostics.json",
    }
    assert original.hex() not in captured.out


def test_ingest_reports_source_errors_without_a_traceback(
    capsys: CaptureFixture[str], tmp_path: Path
) -> None:
    """A missing ingestion source must return status 2 without partial JSON output."""
    from infrastructure.adapters.inbound.cli.main import main

    result = main(
        [
            "ingest",
            str(tmp_path / "missing.pdf"),
            "--parser",
            "pypdf",
            "--output",
            str(tmp_path / "evidence"),
        ]
    )

    captured = capsys.readouterr()
    assert result == 2
    assert captured.out == ""
    assert "Unable to read source" in captured.err
    assert "Traceback" not in captured.err


def test_prepare_models_reports_verified_bundle_without_downloading_in_test(
    capsys: CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    fake_model_bundle: ModelBundle,
) -> None:
    from infrastructure.adapters.inbound.cli.main import main

    def prepared(output: Path) -> ModelBundle:
        return fake_model_bundle

    monkeypatch.setattr(
        "infrastructure.adapters.outbound.document_parser.model_artifacts.prepare_model_bundle",
        prepared,
    )

    result = main(["prepare-ingestion-models", "--output", "/unused"])

    captured = capsys.readouterr()
    assert result == 0
    assert captured.err == ""
    assert json.loads(captured.out) == {
        "bundle_sha256": fake_model_bundle.digest,
        "files": 9,
        "output": str(fake_model_bundle.root),
    }


def test_index_runs_the_operational_composition_and_prints_safe_metadata(
    capsys: CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The technical index command must not expose embeddings or credentials on stdout."""
    from application.use_cases.build_retrieval_index_use_case import IndexBuildResult
    from infrastructure.adapters.inbound.cli.main import main

    called: dict[str, object] = {}

    async def publish(**kwargs: object) -> IndexBuildResult:
        called.update(kwargs)
        return IndexBuildResult(collection="allianz-corpus-123", chunk_count=42)

    monkeypatch.setattr(
        "infrastructure.adapters.inbound.cli.main.build_and_publish_retrieval_index", publish
    )

    result = main(
        [
            "index",
            "--document-hash",
            "a" * 64,
            "--parser",
            "docling-2.124.0-example",
            "--evidence-root",
            str(tmp_path / "evidence"),
            "--profile",
            "structured",
            "--qdrant-url",
            "http://127.0.0.1:6333",
        ]
    )

    captured = capsys.readouterr()
    assert result == 0
    assert captured.err == ""
    assert json.loads(captured.out) == {"chunk_count": 42, "collection": "allianz-corpus-123"}
    assert called == {
        "document_hash": "a" * 64,
        "evidence_root": tmp_path / "evidence",
        "parser": "docling-2.124.0-example",
        "profile_name": "structured",
        "qdrant_url": "http://127.0.0.1:6333",
    }


def test_compare_parsers_writes_a_report_with_timings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    """The CLI must emit a JSON comparison report and persist it under --output."""
    from pypdf import PdfWriter

    from infrastructure.adapters.inbound.cli.main import main

    source = tmp_path / "manual.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(str(source))

    class _FakeExtraction:
        def __init__(self, parser: str, text: str = "hola") -> None:
            self.parser = parser
            self.warnings: tuple[str, ...] = ()
            self.assets: tuple[object, ...] = ()
            self.pages: tuple[object, ...] = ()
            self.manifest = type(
                "_M",
                (),
                {"sha256": "a" * 64, "document_id": "sha256:" + "a" * 64, "page_count": 1},
            )()
            self._text = text

        @property
        def page_count(self) -> int:
            return 1

        def text(self) -> str:
            return self._text

    def fake_pypdf_parse(_self: object, _path: Path) -> object:
        return _FakeExtraction("pypdf-6.16.2", "a b c")

    def fake_docling_parse(_self: object, _path: Path) -> object:
        return _FakeExtraction("docling-2.124.0-test", "a b")

    monkeypatch.setattr(
        "infrastructure.adapters.outbound.document_parser.pypdf_parser.PypdfDocumentParser.parse",
        fake_pypdf_parse,
    )
    monkeypatch.setattr(
        "infrastructure.adapters.outbound.document_parser.docling_parser.DoclingParser.parse",
        fake_docling_parse,
    )

    out = tmp_path / "reports"
    result = main(["compare-parsers", str(source), "--output", str(out)])

    captured = capsys.readouterr()
    assert result == 0
    report_file = out / ("a" * 64 + ".comparison.json")
    assert report_file.exists()
    body = json.loads(report_file.read_text(encoding="utf-8"))
    assert body["page_count"] == 1
    assert "timings_seconds" in body
    assert body["timings_seconds"]["pypdf"] >= 0
    assert body["timings_seconds"]["docling"] >= 0
    assert body["parsers"] == ["docling-2.124.0-test", "pypdf-6.16.2"]
    parsed_stdout = json.loads(captured.out)
    assert parsed_stdout["report"] == str(report_file)


def test_index_rollback_switches_active_alias(
    monkeypatch: pytest.MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    """The rollback CLI must invoke the builder and print the resulting alias state."""
    from infrastructure.adapters.inbound.cli.main import main
    from infrastructure.adapters.outbound.retriever import index_builder

    class _StubBuilder:
        def __init__(self, **_kwargs: object) -> None:
            pass

        async def rollback_alias(self, collection: str) -> str:
            return collection

        async def _active_collection(self) -> str:
            return "allianz-target-collection"

    monkeypatch.setattr(index_builder, "QdrantIndexBuilder", _StubBuilder)
    result = main(["index-rollback", "--collection", "allianz-target-collection"])

    captured = capsys.readouterr()
    assert result == 0
    body = json.loads(captured.out)
    assert body["collection"] == "allianz-target-collection"
    assert body["active_alias"] == "allianz-target-collection"


def test_index_rollback_reports_publication_errors(
    monkeypatch: pytest.MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    """The rollback CLI must surface Qdrant publication failures as exit code 2."""
    from infrastructure.adapters.inbound.cli.main import main
    from infrastructure.adapters.outbound.retriever import index_builder
    from infrastructure.adapters.outbound.retriever.index_builder import (
        IndexPublicationError,
    )

    class _FailingBuilder:
        def __init__(self, **_kwargs: object) -> None:
            pass

        async def rollback_alias(self, collection: str) -> str:
            raise IndexPublicationError(f"cannot rollback to {collection}")

    monkeypatch.setattr(index_builder, "QdrantIndexBuilder", _FailingBuilder)
    result = main(["index-rollback", "--collection", "allianz-broken"])

    captured = capsys.readouterr()
    assert result == 2
    assert "cannot rollback to allianz-broken" in captured.err


def test_list_index_versions_handles_missing_signature(
    monkeypatch: pytest.MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    """The list command must not crash when a collection has no index_signature."""
    from infrastructure.adapters.inbound.cli.main import main

    class _FakeCollections:
        def __init__(self, names: list[str]) -> None:
            self.collections = [type("_E", (), {"name": name})() for name in names]

    class _FakeInfo:
        def __init__(self, metadata: object) -> None:
            self.config = type("_C", (), {"metadata": metadata})()

    class _FakeClient:
        async def __aenter__(self) -> "_FakeClient":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def get_collections(self) -> _FakeCollections:
            return _FakeCollections(["with", "without"])

        async def get_collection(self, name: str) -> _FakeInfo:
            if name == "with":
                return _FakeInfo(
                    {
                        "index_signature": {
                            "document_hash": "a" * 64,
                            "parser": "pypdf-6.16.2",
                            "chunker": "{}",
                            "embedding_model": "text-embedding-3-small",
                            "dimensions": 1536,
                            "lexical_language": "spanish",
                        }
                    }
                )
            return _FakeInfo({"other": "metadata"})

        async def get_aliases(self) -> object:
            class _Aliases:
                def __init__(self) -> None:
                    self.aliases = [
                        type(
                            "_A",
                            (),
                            {"alias_name": "allianz-manual-active", "collection_name": "with"},
                        )()
                    ]

            return _Aliases()

        async def close(self) -> None:
            return None

    monkeypatch.setattr(
        "qdrant_client.AsyncQdrantClient", lambda **_kwargs: _FakeClient()
    )
    result = main(["list-index-versions"])

    captured = capsys.readouterr()
    assert result == 0
    body = json.loads(captured.out)
    assert body[0]["active_alias"] == "with"
    versions = body[0]["versions"]
    assert {row["collection"] for row in versions} == {"with", "without"}
    by_collection = {row["collection"]: row for row in versions}
    assert by_collection["with"]["index_signature"] is not None
    assert by_collection["without"]["index_signature"] is None
