"""Structured local extraction with independently rendered original page evidence."""

import json
import logging
import math
from hashlib import sha256
from importlib.metadata import version
from io import BytesIO
from pathlib import Path

from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.datamodel.base_models import ConversionStatus, DocumentStream, InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc.common.content_layer import ContentLayer
from docling_core.types.doc.document import DoclingDocument
from docling_core.types.doc.items.node import DocItem
from docling_core.types.doc.items.table.table import TableItem
from docling_core.types.doc.items.text import SectionHeaderItem, TextItem

from domain.models.evidence import BinaryAsset, ElementEvidence, Extraction, PageEvidence
from infrastructure.adapters.outbound.document_parser.page_renderer import (
    normalize_layout_pdf,
    render_page_bytes,
)
from infrastructure.adapters.outbound.pdf_source import open_pdf_source

_LOG = logging.getLogger(__name__)


class DoclingParser:
    """Use PDFium layout, Latin RapidOCR on CPU, and conservative review diagnostics."""

    def __init__(self) -> None:
        options = PdfPipelineOptions(
            ocr_options=RapidOcrOptions(backend="torch", lang=["latin"]),
            accelerator_options=AcceleratorOptions(device=AcceleratorDevice.CPU, num_threads=4),
            generate_page_images=False,
            generate_picture_images=False,
        )
        self._configuration = {
            "adapter_revision": 1,
            "backend": "PyPdfiumDocumentBackend",
            "renderer": {"name": "pypdfium2", "scale": 2, "draw_annots": True},
            "ocr": {"engine": "RapidOCR", "backend": "torch", "languages": ["latin"]},
            "coordinates": "visible-page-points-top-left-ltrb",
            "layout_input": "zero-origin-visible-crop-rotation-baked-if-needed",
            "versions": {
                name: version(name)
                for name in (
                    "docling",
                    "docling-core",
                    "docling-ibm-models",
                    "pypdfium2",
                    "pypdf",
                    "rapidocr",
                    "torch",
                    "torchvision",
                    "omegaconf",
                    "pillow",
                )
            },
            "pipeline": options.model_dump(mode="json"),
        }
        configuration = _json_bytes(self._configuration)
        fingerprint = sha256(configuration).hexdigest()[:16]
        self.parser = (
            f"docling-{version('docling')}-pdfium-{version('pypdfium2')}"
            f"-rapidocr-latin-torch-r1-{fingerprint}"
        )
        self._converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    backend=PyPdfiumDocumentBackend, pipeline_options=options
                ),
            }
        )

    def parse(self, source: Path) -> Extraction:
        """Retain every physical page, including failed OCR, from one source snapshot."""
        opened = open_pdf_source(source)
        data = opened.data
        layout_data = normalize_layout_pdf(data)
        warnings: list[str] = []
        document = DoclingDocument(name=source.stem)
        status = "failed"
        errors: list[dict[str, object]] = []
        _LOG.info(
            "Converting %s (%d pages) with %s", source.name, opened.manifest.page_count, self.parser
        )
        try:
            converted = self._converter.convert(
                DocumentStream(name=source.name, stream=BytesIO(layout_data)),
                raises_on_error=False,
            )
            document = converted.document
            status = converted.status.value
            errors = [error.model_dump(mode="json") for error in converted.errors]
            if converted.status != ConversionStatus.SUCCESS:
                warnings.append(f"Docling conversion status: {status}; review original pages")
            for error in converted.errors:
                warnings.append(
                    f"Docling {error.module_name} page {error.page_no}: {error.error_message}"
                )
        except Exception as error:
            # Preserve original evidence when a local OCR/model engine fails. Never mark it success.
            warnings.append(f"Docling conversion failed: {type(error).__name__}: {error}")
            errors.append({"exception": type(error).__name__, "message": str(error)})
        assets = [
            BinaryAsset("original.pdf", data),
            BinaryAsset("configuration.json", _json_bytes(self._configuration)),
        ]
        if layout_data != data:
            assets.append(BinaryAsset("layout-input.pdf", layout_data))
            warnings.append("Layout input crop/rotation normalized; original.pdf is unchanged")
        pages: list[PageEvidence] = []
        projected = _elements_by_page(document, opened.manifest.document_id, warnings)
        for number in range(1, opened.manifest.page_count + 1):
            png, width, height = render_page_bytes(data, number)
            image_path = f"pages/{number}.png"
            assets.append(BinaryAsset(image_path, png))
            elements = tuple(projected.get(number, []))
            text = "\n\n".join(element.text for element in elements if element.text)
            if number not in document.pages:
                warnings.append(f"Page {number} missing from Docling output; review original image")
            if len(text.strip()) < 80:
                warnings.append(
                    f"Page {number} has little extracted text; OCR may be absent or incomplete; "
                    "review original image"
                )
            if any(element.kind == "picture" for element in elements):
                warnings.append(
                    f"Page {number} contains picture evidence; OCR/layout may omit visual content; "
                    "review original image"
                )
            if any(element.kind == "table" for element in elements):
                warnings.append(
                    f"Page {number} contains an unverified table; review labels, merged cells and "
                    "footnotes against original image before using it as rules"
                )
            regions = tuple(region for element in elements for region in element.regions)
            pages.append(
                PageEvidence(
                    evidence_id=f"{opened.manifest.document_id}:page:{number}",
                    document_hash=opened.manifest.sha256,
                    pdf_page=number,
                    text=text,
                    printed_label=None,
                    image_path=image_path,
                    regions=regions,
                    elements=elements,
                    width=width,
                    height=height,
                )
            )
            if number % 10 == 0 or number == opened.manifest.page_count:
                _LOG.info("Retained original render %d/%d", number, opened.manifest.page_count)
        assets.extend(
            (
                BinaryAsset("document.json", document.model_dump_json().encode()),
                BinaryAsset(
                    "document.md",
                    document.export_to_markdown(
                        included_content_layers=set(ContentLayer),
                    ).encode(),
                ),
                BinaryAsset(
                    "diagnostics.json",
                    _json_bytes(
                        {
                            "status": status,
                            "errors": errors,
                            "warnings": warnings,
                            "physical_pages": opened.manifest.page_count,
                            "docling_pages": sorted(document.pages),
                        }
                    ),
                ),
            )
        )
        return Extraction(
            opened.manifest, tuple(pages), self.parser, tuple(warnings), tuple(assets)
        )


def _elements_by_page(
    document: DoclingDocument,
    document_id: str,
    warnings: list[str],
) -> dict[int, list[ElementEvidence]]:
    result: dict[int, list[ElementEvidence]] = {}
    section: str | None = None
    page_sections: dict[int, str | None] = {}
    seen: set[str] = set()
    # Docling 2.124 deprecates attribute access to the still-serialized furniture root.
    furniture = document.__dict__["furniture"]
    for root, is_furniture in ((document.body, False), (furniture, True)):
        for item, _ in document.iterate_items(root=root, included_content_layers=set(ContentLayer)):
            if not isinstance(item, DocItem) or item.self_ref in seen:
                continue
            seen.add(item.self_ref)
            if isinstance(item, SectionHeaderItem):
                section = item.text
            if not is_furniture:
                for provenance in item.prov:
                    page_sections[provenance.page_no] = section
            text = item.text if isinstance(item, TextItem) else ""
            if isinstance(item, TableItem):
                text = item.export_to_markdown(doc=document)
            reference = item.self_ref.removeprefix("#/").replace("/", ":")
            page_regions: dict[int, list[tuple[float, float, float, float]]] = {}
            for provenance in item.prov:
                number = provenance.page_no
                page = document.pages.get(number)
                if page is None:
                    warnings.append(
                        f"Element {reference} has missing page {number}; no region stored"
                    )
                    continue
                bbox = provenance.bbox.to_top_left_origin(page.size.height)
                region = (bbox.l, bbox.t, bbox.r, bbox.b)
                if (
                    not all(math.isfinite(value) for value in region)
                    or not (0 <= bbox.l < bbox.r <= page.size.width + 0.01)
                    or not (0 <= bbox.t < bbox.b <= page.size.height + 0.01)
                ):
                    warnings.append(
                        f"Page {number} element {reference} invalid region; review image"
                    )
                    page_regions.setdefault(number, [])
                    continue
                page_regions.setdefault(number, []).append(region)
            if not item.prov:
                warnings.append(
                    f"Element {reference} has no provenance; retained only in document.json"
                )
            for number, regions in page_regions.items():
                result.setdefault(number, []).append(
                    ElementEvidence(
                        element_id=f"{document_id}:element:{reference}",
                        kind=item.label.value,
                        text=text,
                        section=page_sections.get(number) if is_furniture else section,
                        content_layer=item.content_layer.value,
                        regions=tuple(regions),
                    )
                )
    return result


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
