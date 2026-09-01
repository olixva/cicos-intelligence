"""Pinned model bundles make the neural parser identity reproducible and offline."""

import json
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest

from infrastructure.adapters.outbound.document_parser.model_artifacts import ArtifactManifest


def _manifest(*, revision: str = "a" * 40, model_data: bytes = b"layout") -> ArtifactManifest:
    from infrastructure.adapters.outbound.document_parser.model_artifacts import (
        ArtifactFile,
        ArtifactManifest,
        ArtifactSource,
    )

    return ArtifactManifest(
        schema_version=1,
        sources=(
            ArtifactSource("layout", "huggingface", "example/layout", revision),
            ArtifactSource("table", "huggingface", "example/table", "b" * 40),
            ArtifactSource("rapidocr", "modelscope", "RapidAI/RapidOCR", "v3.9.2"),
        ),
        files=(
            ArtifactFile(
                "layout_model",
                "docling-project--docling-layout-heron/model.safetensors",
                sha256(model_data).hexdigest(),
                len(model_data),
            ),
            ArtifactFile("layout_config", "layout-config.json", sha256(b"c").hexdigest(), 1),
            ArtifactFile("layout_preprocessor", "layout-pre.json", sha256(b"p").hexdigest(), 1),
            ArtifactFile("table_model", "table-model.bin", sha256(b"t").hexdigest(), 1),
            ArtifactFile("table_config", "table-config.json", sha256(b"q").hexdigest(), 1),
            ArtifactFile("ocr_detection", "RapidOcr/det.pth", sha256(b"d").hexdigest(), 1),
            ArtifactFile("ocr_classification", "RapidOcr/cls.pth", sha256(b"s").hexdigest(), 1),
            ArtifactFile("ocr_recognition", "RapidOcr/rec.pth", sha256(b"r").hexdigest(), 1),
            ArtifactFile("ocr_dictionary", "RapidOcr/latin.txt", sha256(b"l").hexdigest(), 1),
        ),
    )


def _write_bundle(root: Path, manifest: ArtifactManifest, *, model_data: bytes = b"layout") -> None:
    data_by_role = {
        "layout_model": model_data,
        "layout_config": b"c",
        "layout_preprocessor": b"p",
        "table_model": b"t",
        "table_config": b"q",
        "ocr_detection": b"d",
        "ocr_classification": b"s",
        "ocr_recognition": b"r",
        "ocr_dictionary": b"l",
    }
    for artifact in manifest.files:
        target = root / artifact.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data_by_role[artifact.role])
    (root / "bundle-manifest.json").write_bytes(manifest.canonical_bytes())


def test_model_revision_and_file_hash_change_bundle_and_parser_identity(tmp_path: Path) -> None:
    """A model pin is part of effective parser identity, rather than only package versions."""
    from infrastructure.adapters.outbound.document_parser.docling_parser import DoclingParser
    from infrastructure.adapters.outbound.document_parser.model_artifacts import load_model_bundle

    first_manifest = _manifest()
    second_manifest = replace(
        first_manifest,
        sources=(
            replace(first_manifest.sources[0], revision="c" * 40),
            *first_manifest.sources[1:],
        ),
        files=(
            replace(first_manifest.files[0], sha256=sha256(b"changed").hexdigest(), size=7),
            *first_manifest.files[1:],
        ),
    )
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    _write_bundle(first_root, first_manifest)
    _write_bundle(second_root, second_manifest, model_data=b"changed")

    first = DoclingParser(model_bundle=load_model_bundle(first_root, first_manifest))
    second = DoclingParser(model_bundle=load_model_bundle(second_root, second_manifest))

    assert first_manifest.digest != second_manifest.digest
    assert first.parser != second.parser


def test_bundle_identity_is_path_independent_and_manifest_has_no_null_pin(tmp_path: Path) -> None:
    from infrastructure.adapters.outbound.document_parser.model_artifacts import load_model_bundle

    manifest = _manifest()
    roots = (tmp_path / "one", tmp_path / "elsewhere" / "two")
    for root in roots:
        _write_bundle(root, manifest)

    first = load_model_bundle(roots[0], manifest)
    second = load_model_bundle(roots[1], manifest)

    assert first.digest == second.digest == manifest.digest
    assert str(tmp_path) not in first.identity_record
    assert all(source.revision for source in manifest.sources)

    record = json.loads(manifest.canonical_bytes())
    record["sources"][0]["revision"] = None
    with pytest.raises(ValueError, match="revision"):
        ArtifactManifest.from_record(record)


def test_bundle_rejects_symlink_before_reading_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from infrastructure.adapters.outbound.document_parser.model_artifacts import load_model_bundle

    manifest = _manifest()
    _write_bundle(tmp_path / "bundle", manifest)
    artifact = tmp_path / "bundle" / manifest.files[0].path
    outside = tmp_path / "outside"
    outside.write_bytes(b"layout")
    artifact.unlink()
    artifact.symlink_to(outside)
    read_bytes = Path.read_bytes

    def reject_symlink_read(path: Path) -> bytes:
        if path.is_symlink():
            raise AssertionError("model symlink was read")
        return read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", reject_symlink_read)
    with pytest.raises(ValueError, match="symlink"):
        load_model_bundle(tmp_path / "bundle", manifest)


def test_missing_default_bundle_fails_with_provisioning_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from infrastructure.adapters.outbound.document_parser.docling_parser import DoclingParser

    monkeypatch.setenv("ALLIANZ_DOCLING_ARTIFACTS", str(tmp_path / "absent"))
    with pytest.raises(ValueError, match="prepare-ingestion-models"):
        DoclingParser()
