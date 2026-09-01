"""Pinned, path-independent model artifacts for fully offline Docling conversion."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import urllib.request
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import cast

_MANIFEST_NAME = "bundle-manifest.json"
_REQUIRED_ROLES = {
    "layout_model",
    "layout_config",
    "layout_preprocessor",
    "table_model",
    "table_config",
    "ocr_detection",
    "ocr_classification",
    "ocr_recognition",
    "ocr_dictionary",
}


@dataclass(frozen=True)
class ArtifactSource:
    """An immutable upstream revision supplying one group of artifacts."""

    name: str
    provider: str
    repository: str
    revision: str


@dataclass(frozen=True)
class ArtifactFile:
    """One effective model file addressed relative to the bundle root."""

    role: str
    path: str
    sha256: str
    size: int


@dataclass(frozen=True)
class ArtifactManifest:
    """Canonical manifest whose digest is included in parser identity."""

    schema_version: int
    sources: tuple[ArtifactSource, ...]
    files: tuple[ArtifactFile, ...]

    @property
    def digest(self) -> str:
        return sha256(_json_bytes(self._payload())).hexdigest()

    def canonical_bytes(self) -> bytes:
        return _json_bytes({**self._payload(), "bundle_sha256": self.digest})

    def _payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "sources": [asdict(source) for source in self.sources],
            "files": [asdict(artifact) for artifact in self.files],
        }

    @classmethod
    def from_record(cls, value: object) -> ArtifactManifest:
        if not isinstance(value, dict):
            raise ValueError("Model bundle manifest must be a JSON object")
        record = cast(dict[str, object], value)
        if set(record) != {"schema_version", "sources", "files", "bundle_sha256"}:
            raise ValueError("Model bundle manifest fields are invalid")
        raw_sources = record["sources"]
        raw_files = record["files"]
        if record["schema_version"] != 1 or not isinstance(raw_sources, list):
            raise ValueError("Model bundle manifest schema is invalid")
        if not isinstance(raw_files, list):
            raise ValueError("Model bundle file list is invalid")
        sources = tuple(_source(item) for item in cast(list[object], raw_sources))
        files = tuple(_artifact(item) for item in cast(list[object], raw_files))
        manifest = cls(schema_version=1, sources=sources, files=files)
        if record["bundle_sha256"] != manifest.digest:
            raise ValueError("Model bundle manifest digest is invalid")
        _validate_manifest(manifest)
        return manifest


@dataclass(frozen=True)
class ModelBundle:
    """A model root validated once before a converter is constructed."""

    root: Path
    manifest: ArtifactManifest

    @property
    def digest(self) -> str:
        return self.manifest.digest

    @property
    def identity_record(self) -> str:
        return self.manifest.canonical_bytes().decode()

    def path(self, role: str) -> Path:
        artifact = next((item for item in self.manifest.files if item.role == role), None)
        if artifact is None:
            raise ValueError(f"Model bundle role is missing: {role}")
        return self.root / artifact.path


PINNED_MODEL_MANIFEST = ArtifactManifest(
    schema_version=1,
    sources=(
        ArtifactSource(
            "layout",
            "huggingface",
            "docling-project/docling-layout-heron",
            "8f39ad3c0b4c58e9c2d2c84a38465abf757272d8",
        ),
        ArtifactSource(
            "table",
            "huggingface",
            "docling-project/docling-models",
            "fc0f2d45e2218ea24bce5045f58a389aed16dc23",
        ),
        ArtifactSource("rapidocr", "modelscope", "RapidAI/RapidOCR", "v3.9.2"),
    ),
    files=(
        ArtifactFile(
            "layout_config",
            "docling-project--docling-layout-heron/config.json",
            "fdea30805ce2f5666b147fca941dcdd27ad468e27d6ed21902207d3da056a97d",
            3268,
        ),
        ArtifactFile(
            "layout_preprocessor",
            "docling-project--docling-layout-heron/preprocessor_config.json",
            "cd38cd59999e7a95d68e487fbe5132df3d4e5c32a0836add57e6126ba0c4eaf1",
            444,
        ),
        ArtifactFile(
            "layout_model",
            "docling-project--docling-layout-heron/model.safetensors",
            "00333a43451945aaf89db8ca9c0a17e75d1537c17db60fdb91aa95f4c7929e0c",
            171658996,
        ),
        ArtifactFile(
            "table_config",
            "docling-project--docling-models/model_artifacts/tableformer/accurate/tm_config.json",
            "984e122ceb8ccf84d84c9d2882f6f2302a44b4f1e577babd6289892c36f3cffd",
            7060,
        ),
        ArtifactFile(
            "table_model",
            "docling-project--docling-models/model_artifacts/tableformer/accurate/"
            "tableformer_accurate.safetensors",
            "2a7d6c924b3cd12fb99a09280ca9c33a89c5d60b93253617d2e088c1a40374d9",
            212758388,
        ),
        ArtifactFile(
            "ocr_detection",
            "RapidOcr/ch_PP-OCRv4_det_mobile.pth",
            "89622c3f3e76b3ac7d10d9434c1f117a7471dba44723885cc04b49932a740d5b",
            14506268,
        ),
        ArtifactFile(
            "ocr_classification",
            "RapidOcr/ch_ptocr_mobile_v2.0_cls_mobile.pth",
            "bfe13860824b3365c0c7f7ccfcddc8ff11645c60051739ff18bc9913f60c98e1",
            588638,
        ),
        ArtifactFile(
            "ocr_recognition",
            "RapidOcr/latin_PP-OCRv3_rec_mobile.pth",
            "caf8e0f2572a7dea2d901c7f50bd78fc310a4246a655d062b69f30258c15bf90",
            8987979,
        ),
        ArtifactFile(
            "ocr_dictionary",
            "RapidOcr/latin_dict.txt",
            "8e6d4e3629788c35c31f7e530287d6147b549bb7a265bd6708bb281134429e2c",
            468,
        ),
    ),
)


def default_model_bundle() -> ModelBundle:
    """Load a fixed local bundle; this path never performs network access."""
    configured = os.environ.get("ALLIANZ_DOCLING_ARTIFACTS")
    root = (
        Path(configured).expanduser()
        if configured
        else Path.home() / ".cache" / "allianz-rag" / "docling-artifacts-v1"
    )
    if not root.is_dir():
        raise ValueError(
            f"Pinned Docling model bundle not found at {root}. Provision it explicitly with: "
            f"allianz prepare-ingestion-models --output {root}"
        )
    return load_model_bundle(root, PINNED_MODEL_MANIFEST)


def load_model_bundle(
    root: Path, expected: ArtifactManifest = PINNED_MODEL_MANIFEST
) -> ModelBundle:
    """Validate manifest, paths, sizes, and hashes once, before any model is loaded."""
    manifest_path = root / _MANIFEST_NAME
    if _contains_symlink(manifest_path, root):
        raise ValueError("Model bundle manifest contains a symlink")
    try:
        raw_manifest = manifest_path.read_bytes()
        manifest = ArtifactManifest.from_record(json.loads(raw_manifest))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("Model bundle manifest is missing or unreadable") from error
    if raw_manifest != manifest.canonical_bytes() or manifest != expected:
        raise ValueError("Model bundle manifest does not match the pinned artifact set")

    expected_paths = {artifact.path for artifact in manifest.files}
    actual_paths: set[str] = set()
    for entry in root.rglob("*"):
        if entry.is_symlink():
            raise ValueError(f"Model bundle contains a symlink: {entry.relative_to(root)}")
        if entry.is_file():
            actual_paths.add(entry.relative_to(root).as_posix())
    if actual_paths != {*expected_paths, _MANIFEST_NAME}:
        raise ValueError("Model bundle contains missing or unregistered files")

    for artifact in manifest.files:
        path = root / artifact.path
        if _contains_symlink(path, root):
            raise ValueError(f"Model bundle contains a symlink: {artifact.path}")
        digest, size = _hash_file(path)
        if digest != artifact.sha256 or size != artifact.size:
            raise ValueError(f"Model artifact hash or size mismatch: {artifact.path}")
    return ModelBundle(root=root, manifest=manifest)


def prepare_model_bundle(output: Path) -> ModelBundle:
    """Download the exact pinned revisions into an atomic, verified local bundle."""
    output = output.expanduser()
    if output.exists():
        return load_model_bundle(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        for artifact in PINNED_MODEL_MANIFEST.files:
            target = temporary / artifact.path
            target.parent.mkdir(parents=True, exist_ok=True)
            source = _download_artifact(artifact)
            shutil.copyfile(source, target)
        (temporary / _MANIFEST_NAME).write_bytes(PINNED_MODEL_MANIFEST.canonical_bytes())
        load_model_bundle(temporary)
        temporary.rename(output)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return load_model_bundle(output)


def _download_artifact(artifact: ArtifactFile) -> Path:
    if artifact.role.startswith("layout_"):
        filename = artifact.path.removeprefix("docling-project--docling-layout-heron/")
        source = PINNED_MODEL_MANIFEST.sources[0]
        from huggingface_hub import hf_hub_download  # pyright: ignore[reportUnknownVariableType]

        return Path(
            hf_hub_download(repo_id=source.repository, filename=filename, revision=source.revision)
        )
    if artifact.role.startswith("table_"):
        filename = artifact.path.removeprefix("docling-project--docling-models/")
        source = PINNED_MODEL_MANIFEST.sources[1]
        from huggingface_hub import hf_hub_download  # pyright: ignore[reportUnknownVariableType]

        return Path(
            hf_hub_download(repo_id=source.repository, filename=filename, revision=source.revision)
        )
    filename = PurePosixPath(artifact.path).name
    rapid_subpaths = {
        "ocr_detection": "torch/PP-OCRv4/det",
        "ocr_classification": "torch/PP-OCRv4/cls",
        "ocr_recognition": "torch/PP-OCRv4/rec",
        "ocr_dictionary": "paddle/PP-OCRv4/rec/latin_PP-OCRv3_rec_mobile",
    }
    release = PINNED_MODEL_MANIFEST.sources[2].revision
    url = (
        "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/"
        f"{release}/{rapid_subpaths[artifact.role]}/{filename}"
    )
    temporary, _ = urllib.request.urlretrieve(url)  # noqa: S310 - fixed HTTPS host and pin
    return Path(temporary)


def _source(value: object) -> ArtifactSource:
    if not isinstance(value, dict):
        raise ValueError("Model source record is invalid")
    record = cast(dict[str, object], value)
    if set(record) != {
        "name",
        "provider",
        "repository",
        "revision",
    }:
        raise ValueError("Model source record is invalid")
    fields = tuple(record[key] for key in ("name", "provider", "repository", "revision"))
    if not all(isinstance(field, str) and field for field in fields):
        raise ValueError("Every model source revision must be a non-null pin")
    return ArtifactSource(*cast(tuple[str, str, str, str], fields))


def _artifact(value: object) -> ArtifactFile:
    if not isinstance(value, dict):
        raise ValueError("Model artifact record is invalid")
    record = cast(dict[str, object], value)
    if set(record) != {"role", "path", "sha256", "size"}:
        raise ValueError("Model artifact record is invalid")
    role, path, digest, size = (record[key] for key in ("role", "path", "sha256", "size"))
    if (
        not isinstance(role, str)
        or not isinstance(path, str)
        or not isinstance(digest, str)
        or isinstance(size, bool)
        or not isinstance(size, int)
    ):
        raise ValueError("Model artifact fields are invalid")
    return ArtifactFile(role, path, digest, size)


def _validate_manifest(manifest: ArtifactManifest) -> None:
    if manifest.schema_version != 1 or not manifest.sources:
        raise ValueError("Model bundle manifest schema is invalid")
    if any(not source.revision for source in manifest.sources):
        raise ValueError("Every model source revision must be a non-null pin")
    roles = [artifact.role for artifact in manifest.files]
    paths = [artifact.path for artifact in manifest.files]
    if set(roles) != _REQUIRED_ROLES or len(roles) != len(set(roles)):
        raise ValueError("Model artifact roles are missing or duplicated")
    if len(paths) != len(set(paths)):
        raise ValueError("Model artifact paths are duplicated")
    for artifact in manifest.files:
        path = PurePosixPath(artifact.path)
        if (
            path.is_absolute()
            or ".." in path.parts
            or "\\" in artifact.path
            or str(path) != artifact.path
            or re.fullmatch(r"[0-9a-f]{64}", artifact.sha256) is None
            or artifact.size < 0
        ):
            raise ValueError("Model artifact pin is invalid")


def _contains_symlink(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return True
    current = root
    if current.is_symlink():
        return True
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            return True
    return False


def _hash_file(path: Path) -> tuple[str, int]:
    digest = sha256()
    size = 0
    try:
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
    except OSError as error:
        raise ValueError(f"Model artifact is unreadable: {path.name}") from error
    return digest.hexdigest(), size


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
