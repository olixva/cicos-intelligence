"""CLI tests for the golden release machinery.

These tests exercise ``allianz golden validate``, ``freeze`` and
``publish`` against fixture inputs created in a tmp directory. They do
not depend on a real Langfuse server; the publish path is mocked so the
full happy-path roundtrip can be asserted.
"""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest
from pytest import CaptureFixture


def _write_release_artifacts(golden_root: Path) -> Path:
    """Create a fixture golden + a release directory with hashed artifacts."""
    from infrastructure.adapters.outbound.evaluation.golden_schema import (
        canonical_schema_bytes,
    )
    from infrastructure.adapters.outbound.evaluation.release_validation import (
        build_release_manifest,
        canonical_jsonl,
    )

    item = {
        "input": {"text": "Pregunta fixture.", "language": "es", "clarifications": []},
        "expected_output": {
            "reference": "Respuesta fixture.",
            "decisions": {"intent": "question", "answer_status": "answered"},
            "requirements": [{"requirement_id": "req-1", "description": "Cubre el fixture."}],
            "acceptable_alternatives": [],
            "forbidden_facts": ["No inventar reglas."],
            "evidence_requirements": [
                {
                    "requirement_id": "req-1",
                    "any_of": [
                        {
                            "bundle_id": "bundle-and",
                            "all_of": ["fixture-evidence:page:1"],
                        }
                    ],
                }
            ],
        },
        "metadata": {
            "case_id": "fixture-cli-1",
            "family_id": "fixture-cli",
            "partition": "development",
            "review_status": "adjudicated",
            "provenance": {"kind": "technical_fixture", "source_ids": ["test_golden_cli"]},
            "language": "es",
            "expected_intent": "question",
            "review": {
                "reviewer_ids": ["technical-validator-fixture"],
                "independent_resolution_checked": True,
                "evidence_checked": True,
                "adversarial_checked": True,
                "adjudication_note": "Fixture used only to test release CLI.",
                "open_discrepancies": [],
            },
        },
    }
    (golden_root / "development.jsonl").write_text(
        json.dumps(item, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    schema_bytes = canonical_schema_bytes()
    items = [item]
    manifest = build_release_manifest(
        dataset_name="allianz-rag",
        dataset_version="v0-cli-fixture",
        items=items,
        schema=schema_bytes,
        existing_evidence_ids={"fixture-evidence:page:1"},
    )
    release_dir = golden_root / "releases" / "v0-cli-fixture"
    release_dir.mkdir(parents=True, exist_ok=True)
    (release_dir / "items.jsonl").write_bytes(
        canonical_jsonl(items, existing_evidence_ids={"fixture-evidence:page:1"})
    )
    (release_dir / "schema.json").write_bytes(schema_bytes)
    (release_dir / "manifest.json").write_text(
        json.dumps(json.loads(manifest.model_dump_json()), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return release_dir


def test_golden_validate_reports_evidence_pool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    """validate must report schema version, evidence pool and a list of errors."""
    from infrastructure.adapters.inbound.cli.main import main

    golden_root = tmp_path / "golden"
    golden_root.mkdir()
    evidence_root = tmp_path / "evidence"
    document_hash = "b" * 64
    parser_dir = evidence_root / document_hash / "pypdf-6.16.2"
    parser_dir.mkdir(parents=True)
    (parser_dir / "manifest.json").write_text(
        json.dumps(
            {
                "document_id": f"sha256:{document_hash}",
                "sha256": document_hash,
                "filename": f"{document_hash}.pdf",
                "page_count": 1,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (parser_dir / "pages.jsonl").write_text(
        json.dumps(
            {
                "evidence_id": "fixture-evidence:page:1",
                "document_hash": document_hash,
                "pdf_page": 1,
                "text": "demo",
                "regions": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (golden_root / "development.jsonl").write_text(
        json.dumps(
            {
                "input": {"text": "Pregunta.", "language": "es", "clarifications": []},
                "expected_output": {
                    "reference": "Respuesta.",
                    "decisions": {"intent": "question", "answer_status": "answered"},
                    "requirements": [
                        {"requirement_id": "req-1", "description": "Cubre el fixture."}
                    ],
                    "acceptable_alternatives": [],
                    "forbidden_facts": ["No inventar."],
                    "evidence_requirements": [
                        {
                            "requirement_id": "req-1",
                            "any_of": [
                                {
                                    "bundle_id": "bundle-and",
                                    "all_of": ["fixture-evidence:page:1"],
                                }
                            ],
                        }
                    ],
                },
                "metadata": {
                    "case_id": "fixture-cli-1",
                    "family_id": "fixture-cli",
                    "partition": "development",
                    "review_status": "adjudicated",
                    "provenance": {
                        "kind": "technical_fixture",
                        "source_ids": ["test_golden_cli"],
                    },
                    "language": "es",
                    "expected_intent": "question",
                    "review": {
                        "reviewer_ids": ["technical-validator-fixture"],
                        "independent_resolution_checked": True,
                        "evidence_checked": True,
                        "adversarial_checked": True,
                        "adjudication_note": "Fixture used only to test release CLI.",
                        "open_discrepancies": [],
                    },
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    result = main(
        [
            "golden",
            "validate",
            "--golden-root",
            str(golden_root),
            "--evidence-roots",
            str(evidence_root),
        ]
    )

    captured = capsys.readouterr()
    assert result == 0
    body = json.loads(captured.out)
    assert body["item_count"] == 1
    assert body["evidence_pool_size"] == 1
    assert body["errors"] == []


def test_golden_validate_rejects_unfinished_review(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    """Cases without adjudicated review must be reported as errors."""
    from infrastructure.adapters.inbound.cli.main import main

    golden_root = tmp_path / "golden"
    golden_root.mkdir()
    item = {
        "input": {"text": "Pregunta.", "language": "es", "clarifications": []},
        "expected_output": {
            "reference": "Respuesta.",
            "decisions": {"intent": "question", "answer_status": "answered"},
            "requirements": [{"requirement_id": "req-1", "description": "Cubre."}],
            "acceptable_alternatives": [],
            "forbidden_facts": [],
            "evidence_requirements": [
                {
                    "requirement_id": "req-1",
                    "any_of": [{"bundle_id": "bundle-and", "all_of": ["fixture-evidence:page:1"]}],
                }
            ],
        },
        "metadata": {
            "case_id": "fixture-cli-1",
            "family_id": "fixture-cli",
            "partition": "development",
            "review_status": "candidate",
            "provenance": {"kind": "technical_fixture", "source_ids": ["test_golden_cli"]},
            "language": "es",
            "expected_intent": "question",
            "review": {
                "reviewer_ids": ["reviewer-1"],
                "independent_resolution_checked": False,
                "evidence_checked": False,
                "adversarial_checked": False,
                "adjudication_note": "Pending.",
                "open_discrepancies": ["Needs human review."],
            },
        },
    }
    (golden_root / "development.jsonl").write_text(
        json.dumps(item, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    result = main(["golden", "validate", "--golden-root", str(golden_root)])

    captured = capsys.readouterr()
    body = json.loads(captured.out)
    assert result == 2
    assert any("incomplete review" in err for err in body["errors"])


def test_golden_freeze_persists_release_artifacts(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    """freeze must validate and produce items.jsonl, schema.json and manifest.json."""
    from infrastructure.adapters.inbound.cli.main import main

    golden_root = tmp_path / "golden"
    golden_root.mkdir()
    evidence_root = tmp_path / "evidence"
    document_hash = "c" * 64
    parser_dir = evidence_root / document_hash / "pypdf-6.16.2"
    parser_dir.mkdir(parents=True)
    (parser_dir / "manifest.json").write_text(
        json.dumps(
            {
                "document_id": f"sha256:{document_hash}",
                "sha256": document_hash,
                "filename": f"{document_hash}.pdf",
                "page_count": 1,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (parser_dir / "pages.jsonl").write_text(
        json.dumps(
            {
                "evidence_id": "fixture-evidence:page:1",
                "document_hash": document_hash,
                "pdf_page": 1,
                "text": "demo",
                "regions": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (golden_root / "development.jsonl").write_text(
        json.dumps(
            {
                "input": {"text": "Pregunta.", "language": "es", "clarifications": []},
                "expected_output": {
                    "reference": "Respuesta.",
                    "decisions": {"intent": "question", "answer_status": "answered"},
                    "requirements": [
                        {"requirement_id": "req-1", "description": "Cubre el fixture."}
                    ],
                    "acceptable_alternatives": [],
                    "forbidden_facts": ["No inventar."],
                    "evidence_requirements": [
                        {
                            "requirement_id": "req-1",
                            "any_of": [
                                {
                                    "bundle_id": "bundle-and",
                                    "all_of": ["fixture-evidence:page:1"],
                                }
                            ],
                        }
                    ],
                },
                "metadata": {
                    "case_id": "fixture-cli-1",
                    "family_id": "fixture-cli",
                    "partition": "development",
                    "review_status": "adjudicated",
                    "provenance": {
                        "kind": "technical_fixture",
                        "source_ids": ["test_golden_cli"],
                    },
                    "language": "es",
                    "expected_intent": "question",
                    "review": {
                        "reviewer_ids": ["technical-validator-fixture"],
                        "independent_resolution_checked": True,
                        "evidence_checked": True,
                        "adversarial_checked": True,
                        "adjudication_note": "Fixture used only to test release CLI.",
                        "open_discrepancies": [],
                    },
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    result = main(
        [
            "golden",
            "freeze",
            "--golden-root",
            str(golden_root),
            "--evidence-roots",
            str(evidence_root),
            "--dataset",
            "allianz-rag",
            "--release",
            "v0-cli-fixture",
        ]
    )

    captured = capsys.readouterr()
    body = json.loads(captured.out)
    assert result == 0
    assert body["release"] == "v0-cli-fixture"
    release_dir = golden_root / "releases" / "v0-cli-fixture"
    assert (release_dir / "items.jsonl").exists()
    assert (release_dir / "schema.json").exists()
    assert (release_dir / "manifest.json").exists()
    manifest = json.loads((release_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["item_count"] == 1
    assert (
        manifest["content_sha256"] == sha256((release_dir / "items.jsonl").read_bytes()).hexdigest()
    )


def test_golden_freeze_rejects_existing_release(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    """Freezing twice must fail instead of overwriting an existing release."""
    from infrastructure.adapters.inbound.cli.main import main

    golden_root = tmp_path / "golden"
    golden_root.mkdir()
    evidence_root = tmp_path / "evidence"
    document_hash = "d" * 64
    parser_dir = evidence_root / document_hash / "pypdf-6.16.2"
    parser_dir.mkdir(parents=True)
    (parser_dir / "manifest.json").write_text(
        json.dumps(
            {
                "document_id": f"sha256:{document_hash}",
                "sha256": document_hash,
                "filename": f"{document_hash}.pdf",
                "page_count": 1,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (parser_dir / "pages.jsonl").write_text(
        json.dumps(
            {
                "evidence_id": "fixture-evidence:page:1",
                "document_hash": document_hash,
                "pdf_page": 1,
                "text": "demo",
                "regions": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _write_release_artifacts(golden_root)

    result = main(
        [
            "golden",
            "freeze",
            "--golden-root",
            str(golden_root),
            "--evidence-roots",
            str(evidence_root),
            "--dataset",
            "allianz-rag",
            "--release",
            "v0-cli-fixture",
        ]
    )
    captured = capsys.readouterr()
    assert result == 2
    assert "already exists" in captured.err


def test_golden_publish_calls_langfuse_with_verified_hashes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    """publish must verify both item and schema hashes before calling Langfuse."""
    from infrastructure.adapters.inbound.cli.main import main

    golden_root = tmp_path / "golden"
    golden_root.mkdir()
    _write_release_artifacts(golden_root)

    created: list[dict[str, object]] = []
    item_calls: list[dict[str, object]] = []

    class _FakeLangfuse:
        def __init__(self) -> None:
            pass

        def create_dataset(self, **_kwargs: object) -> None:
            created.append({"dataset": True})

        def create_dataset_item(self, **_kwargs: object) -> None:
            item_calls.append({**_kwargs})

        def flush(self) -> None:
            return None

    monkeypatch.setattr("langfuse.Langfuse", lambda: _FakeLangfuse())

    result = main(
        [
            "golden",
            "publish",
            "--release",
            "v0-cli-fixture",
            "--golden-root",
            str(golden_root),
        ]
    )

    captured = capsys.readouterr()
    assert result == 0
    body = json.loads(captured.out)
    assert body["uploaded_items"] == 1
    assert item_calls and item_calls[0]["dataset_name"] == "allianz-rag"
    assert created  # dataset was created at least once
