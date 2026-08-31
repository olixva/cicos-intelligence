"""Baseline page extraction backed by pypdf."""

from pathlib import Path

from pypdf import __version__ as pypdf_version

from domain.models.evidence import Extraction, PageEvidence
from infrastructure.adapters.outbound.pdf_source import open_pdf_source


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
        return Extraction(
            manifest=opened.manifest,
            pages=tuple(pages),
            parser=self.parser,
            warnings=tuple(warnings),
        )
