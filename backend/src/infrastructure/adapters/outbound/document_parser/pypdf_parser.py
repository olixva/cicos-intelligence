"""Baseline page extraction backed by pypdf."""

from pathlib import Path

from pypdf import __version__ as pypdf_version

from domain.models.evidence import BinaryAsset, Extraction, PageEvidence
from infrastructure.adapters.outbound.pdf_source import open_pdf_source

# Contrato unificado de publicación: cada parser publica el PDF original
# bajo la ruta canónica `original.pdf`. El catálogo de fuente y la API
# `/api/v1/manual/pdf` dependen de esta ruta; los tests de contrato
# (T2) la verifican en ambos parsers.
ORIGINAL_PDF_ASSET_PATH = "original.pdf"


class PypdfDocumentParser:
    """Extract text from each physical page without inventing layout evidence."""

    parser = f"pypdf-{pypdf_version}"

    def parse(self, source: Path) -> Extraction:
        """Extract all pages from the exact bytes used to derive the manifest hash."""
        opened = open_pdf_source(source)
        pages: list[PageEvidence] = []
        warnings: list[str] = []
        for number, page in enumerate(opened.reader.pages, start=1):
            text = page.extract_text() or ""
            if not text:
                warnings.append(f"Page {number} did not yield extractable text")
            pages.append(
                PageEvidence(
                    evidence_id=f"{opened.manifest.document_id}:page:{number}",
                    document_hash=opened.manifest.sha256,
                    pdf_page=number,
                    text=text,
                    printed_label=None,
                    image_path=None,
                    regions=(),
                )
            )
        original_asset = BinaryAsset(path=ORIGINAL_PDF_ASSET_PATH, data=opened.data)
        return Extraction(
            manifest=opened.manifest,
            pages=tuple(pages),
            parser=self.parser,
            warnings=tuple(warnings),
            assets=(original_asset,),
        )
