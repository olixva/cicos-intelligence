"""Adaptadores de parseo: Docling, bundle de modelos y render de paginas."""

import json
from dataclasses import replace
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.base_models import ConversionStatus, InputFormat
from docling.datamodel.document import ConversionResult, InputDocument
from docling.document_converter import DocumentConverter
from docling_core.types.doc.base import BoundingBox, CoordOrigin, Size
from docling_core.types.doc.common.content_layer import ContentLayer
from docling_core.types.doc.common.reference import ProvenanceItem
from docling_core.types.doc.document import DoclingDocument
from docling_core.types.doc.labels import DocItemLabel
from PIL import Image
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject, RectangleObject

from infrastructure.adapters.outbound.document_parser.model_artifacts import (
    ArtifactManifest,
    ModelBundle,
)

# --------------------------------------------------------------------------
# Test our projection of real Docling models; neural conversion is the slow boundary.
# --------------------------------------------------------------------------


def _two_pages(path: Path) -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=100)
    writer.add_blank_page(width=200, height=100)
    writer.write(path)
    return path.read_bytes()


def test_projection_retains_furniture_geometry_sections_and_missing_pages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_model_bundle: ModelBundle,
) -> None:
    """Dropping furniture, trusting missing OCR, or double-flipping display boxes loses evidence."""
    from infrastructure.adapters.outbound.document_parser.docling_parser import DoclingParser

    source = tmp_path / "source.pdf"
    original = _two_pages(source)
    document = DoclingDocument(name="Fixture")
    document.add_page(1, Size(width=200, height=100))
    provenance = ProvenanceItem(
        page_no=1,
        charspan=(0, 8),
        bbox=BoundingBox(l=10, t=80, r=90, b=60, coord_origin=CoordOrigin.BOTTOMLEFT),
    )
    document.add_heading("Coverage", prov=provenance)
    document.add_text(label=DocItemLabel.TEXT, text="Conditions", prov=provenance)
    document.add_text(
        label=DocItemLabel.FOOTNOTE,
        text="Critical note",
        prov=provenance,
        content_layer=ContentLayer.FURNITURE,
    )
    input_doc = InputDocument(
        path_or_stream=BytesIO(original),
        format=InputFormat.PDF,
        backend=PyPdfiumDocumentBackend,
        filename=source.name,
    )
    result = ConversionResult(
        input=input_doc, document=document, status=ConversionStatus.PARTIAL_SUCCESS
    )

    def converted(*args: Any, **kwargs: Any) -> ConversionResult:
        source.write_bytes(b"changed after snapshot")
        return result

    monkeypatch.setattr(DocumentConverter, "convert", converted)
    extraction = DoclingParser(model_bundle=fake_model_bundle).parse(source)
    assert [page.pdf_page for page in extraction.pages] == [1, 2]
    page = extraction.pages[0]
    assert "Critical note" in page.text
    assert len(page.elements) == 3
    note = next(element for element in page.elements if element.kind == "footnote")
    assert note.section == "Coverage"
    assert note.content_layer == "furniture"
    assert note.regions == ((10.0, 20.0, 90.0, 40.0),)
    assert note.element_id.startswith(f"{extraction.manifest.document_id}:element:")
    assert (page.width, page.height) == (200.0, 100.0)
    assert any("Page 2" in warning and "missing" in warning for warning in extraction.warnings)
    assert any("partial_success" in warning for warning in extraction.warnings)
    assert (
        next(asset.data for asset in extraction.assets if asset.path == "original.pdf") == original
    )
    assert all(not asset.path.startswith(str(tmp_path)) for asset in extraction.assets)


def test_ocr_failure_is_declared_without_dropping_original_pages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_model_bundle: ModelBundle,
) -> None:
    """A conversion exception must retain each rendered page and an explicit failure warning."""
    from infrastructure.adapters.outbound.document_parser.docling_parser import DoclingParser

    source = tmp_path / "source.pdf"
    original = _two_pages(source)

    def failed(*args: Any, **kwargs: Any) -> ConversionResult:
        raise RuntimeError("OCR engine unavailable")

    monkeypatch.setattr(DocumentConverter, "convert", failed)
    extraction = DoclingParser(model_bundle=fake_model_bundle).parse(source)
    assert len(extraction.pages) == 2
    assert all(page.image_path for page in extraction.pages)
    assert any("OCR engine unavailable" in warning for warning in extraction.warnings)
    assert any("failed" in warning for warning in extraction.warnings)
    assert (
        next(asset.data for asset in extraction.assets if asset.path == "original.pdf") == original
    )


def test_furniture_uses_the_section_active_on_its_own_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_model_bundle: ModelBundle
) -> None:
    """Furniture iterated after the body must not inherit the document's final section."""
    from infrastructure.adapters.outbound.document_parser.docling_parser import DoclingParser

    source = tmp_path / "source.pdf"
    original = _two_pages(source)
    document = DoclingDocument(name="Fixture")
    for number in (1, 2):
        document.add_page(number, Size(width=200, height=100))
    first = ProvenanceItem(
        page_no=1,
        charspan=(0, 8),
        bbox=BoundingBox(l=10, t=80, r=90, b=60, coord_origin=CoordOrigin.BOTTOMLEFT),
    )
    second = first.model_copy(update={"page_no": 2})
    document.add_heading("Coverage", prov=first)
    document.add_text(
        label=DocItemLabel.PAGE_FOOTER,
        text="Page one",
        prov=first,
        content_layer=ContentLayer.FURNITURE,
        parent=document.__dict__["furniture"],
    )
    document.add_heading("Exclusions", prov=second)
    input_doc = InputDocument(
        path_or_stream=BytesIO(original),
        format=InputFormat.PDF,
        backend=PyPdfiumDocumentBackend,
        filename=source.name,
    )
    converted = ConversionResult(
        input=input_doc, document=document, status=ConversionStatus.SUCCESS
    )

    def convert(*args: Any, **kwargs: Any) -> ConversionResult:
        return converted

    monkeypatch.setattr(DocumentConverter, "convert", convert)

    extraction = DoclingParser(model_bundle=fake_model_bundle).parse(source)

    footer = next(
        element for element in extraction.pages[0].elements if element.kind == "page_footer"
    )
    assert footer.section == "Coverage"


def test_configuration_records_effective_ocr_backend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_model_bundle: ModelBundle
) -> None:
    """Changing the RapidOCR runtime backend must change persisted parser configuration."""
    from infrastructure.adapters.outbound.document_parser.docling_parser import DoclingParser

    source = tmp_path / "source.pdf"
    original = _two_pages(source)
    document = DoclingDocument(name="Fixture")
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

    extraction = DoclingParser(model_bundle=fake_model_bundle).parse(source)
    configuration = json.loads(
        next(asset.data for asset in extraction.assets if asset.path == "configuration.json")
    )

    assert configuration["ocr"] == {
        "backend": "torch",
        "engine": "RapidOCR",
        "languages": ["latin"],
    }


def test_source_alias_does_not_change_docling_assets_or_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_model_bundle: ModelBundle,
) -> None:
    """Docling's raw exports must use content identity rather than the caller's filename."""
    from infrastructure.adapters.outbound.document_parser.docling_parser import DoclingParser
    from infrastructure.adapters.outbound.evidence_repository.filesystem_repository import (
        FilesystemEvidenceRepository,
    )

    first = tmp_path / "a.pdf"
    original = _two_pages(first)
    second = tmp_path / "b.pdf"
    second.write_bytes(original)

    def convert(stream: Any, **kwargs: Any) -> ConversionResult:
        document = DoclingDocument(name=Path(stream.name).stem)
        return ConversionResult(
            input=InputDocument(
                path_or_stream=BytesIO(original),
                format=InputFormat.PDF,
                backend=PyPdfiumDocumentBackend,
                filename=stream.name,
            ),
            document=document,
            status=ConversionStatus.SUCCESS,
        )

    monkeypatch.setattr(DocumentConverter, "convert", convert)
    parser = DoclingParser(model_bundle=fake_model_bundle)

    first_extraction = parser.parse(first)
    second_extraction = parser.parse(second)

    assert first_extraction.manifest.filename == "a.pdf"
    assert second_extraction.manifest.filename == "b.pdf"
    assert first_extraction.assets == second_extraction.assets
    repository = FilesystemEvidenceRepository(tmp_path / "evidence", parser.parser)
    assert repository.publish(first_extraction) == repository.publish(second_extraction)


# --------------------------------------------------------------------------
# Pinned model bundles make the neural parser identity reproducible and offline.
# --------------------------------------------------------------------------


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


# --------------------------------------------------------------------------
# Known PDF geometry, independent of neural layout predictions.
# --------------------------------------------------------------------------


def colored_page(path: Path, rotation: int) -> None:
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=200)
    page.cropbox = RectangleObject((50, 30, 250, 130))
    page.rotate(rotation)
    stream = DecodedStreamObject()
    # A red box at crop-local x=20..40, y=10..30 (PDF bottom-left coordinates).
    stream.set_data(b"1 0 0 rg 70 40 20 20 re f")
    page[NameObject("/Contents")] = writer._add_object(stream)  # pyright: ignore[reportPrivateUsage]
    writer.write(path)


@pytest.mark.parametrize(
    ("rotation", "size", "red_center"),
    [
        (0, (400, 200), (60, 160)),
        (90, (200, 400), (40, 60)),
        (180, (400, 200), (340, 40)),
        (270, (200, 400), (160, 340)),
    ],
)
def test_renderer_uses_visible_crop_and_rotation(
    tmp_path: Path,
    rotation: int,
    size: tuple[int, int],
    red_center: tuple[int, int],
) -> None:
    """Ignoring a crop offset or applying /Rotate twice moves the red reference box."""
    from infrastructure.adapters.outbound.document_parser.page_renderer import render_page

    source = tmp_path / "geometry.pdf"
    colored_page(source, rotation)
    result = render_page(source, 1, tmp_path / "render.png")
    with Image.open(result) as image:
        assert image.size == size
        assert image.convert("RGB").getpixel(red_center) == (255, 0, 0)
        assert image.convert("RGB").getpixel((0, 0)) == (255, 255, 255)


@pytest.mark.parametrize("number", [0, -1, 2])
def test_renderer_rejects_nonexistent_physical_pages(tmp_path: Path, number: int) -> None:
    """PDF page zero must not accidentally select the last page through negative indexing."""
    from infrastructure.adapters.outbound.document_parser.page_renderer import render_page

    source = tmp_path / "geometry.pdf"
    colored_page(source, 0)
    with pytest.raises(ValueError, match="page"):
        render_page(source, number, tmp_path / "render.png")


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_layout_normalization_keeps_visible_pixels_and_zeroes_crop_offsets(
    tmp_path: Path,
    rotation: int,
) -> None:
    """Layout input normalization must not move crop-local content or retain offsets."""
    from io import BytesIO

    from pypdf import PdfReader

    from infrastructure.adapters.outbound.document_parser.page_renderer import (
        normalize_layout_pdf,
        render_page_bytes,
    )

    source = tmp_path / "geometry.pdf"
    colored_page(source, rotation)
    original = source.read_bytes()
    normalized = normalize_layout_pdf(original)
    page = PdfReader(BytesIO(normalized)).pages[0]
    assert page.rotation == 0
    assert page.cropbox.left == page.cropbox.bottom == 0
    assert render_page_bytes(normalized, 1) == render_page_bytes(original, 1)
