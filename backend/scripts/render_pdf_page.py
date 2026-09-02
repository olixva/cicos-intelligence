"""Render one physical PDF page to PNG for visual transcription.

Deliberately independent from the Docling pipeline: a transcription is
only a useful cross-check when it does not share an extraction path
with the transcription it is compared against.
"""

import argparse
from pathlib import Path

import pypdfium2 as pdfium


def render(source: Path, page: int, output: Path, dpi: int) -> Path:
    """Render the 1-indexed physical page and return the written path."""
    if page < 1:
        raise ValueError("page must be a positive 1-indexed physical page number")
    if dpi <= 0:
        raise ValueError("dpi must be positive")
    document = pdfium.PdfDocument(source)
    if page > len(document):
        raise ValueError(f"page {page} is beyond the {len(document)}-page document")
    image = document[page - 1].render(scale=dpi / 72).to_pil()
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--page", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dpi", type=int, default=300)
    args = parser.parse_args()
    print(render(args.source, args.page, args.output, args.dpi))


if __name__ == "__main__":
    main()
