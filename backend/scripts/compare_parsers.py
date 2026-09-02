"""Parser publication comparison helpers.

Used by the T2 ingestion publication contract to surface textual coverage,
asset inventory and structural differences between two parser outputs of the
same source document. The comparison never mutates the inputs; it operates
on already-published ``Extraction`` instances and is safe to call from tests
or from the CLI entry point.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from domain.models.evidence import ElementEvidence, Extraction, PageEvidence


def _text_words(text: str) -> frozenset[str]:
    return frozenset(word for word in text.split() if word)


def _line_count(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip())


def _element_kind_counts(elements: Iterable[ElementEvidence]) -> Counter[str]:
    return Counter(element.kind for element in elements)


def _coverage(source_words: frozenset[str], reference_words: frozenset[str]) -> float:
    if not source_words:
        return 1.0 if not reference_words else 0.0
    return len(source_words & reference_words) / len(source_words)


def compare_extractions(left: Extraction, right: Extraction) -> dict[str, object]:
    """Report structural differences and textual coverage between two publications."""
    if left.manifest.document_id != right.manifest.document_id:
        raise ValueError(
            "Cannot compare publications of different documents "
            f"({left.manifest.document_id} vs {right.manifest.document_id})"
        )

    left_words = _text_words(_pages_text(left.pages))
    right_words = _text_words(_pages_text(right.pages))

    left_assets = {asset.path for asset in left.assets}
    right_assets = {asset.path for asset in right.assets}

    left_kinds = _element_kind_counts(_all_elements(left.pages))
    right_kinds = _element_kind_counts(_all_elements(right.pages))

    return {
        "document_id": left.manifest.document_id,
        "document_sha256": left.manifest.sha256,
        "page_count": left.manifest.page_count,
        "parsers": sorted({left.parser, right.parser}),
        "warnings": {
            "left": list(left.warnings),
            "right": list(right.warnings),
        },
        "line_counts": {
            "left": _line_count(_pages_text(left.pages)),
            "right": _line_count(_pages_text(right.pages)),
        },
        "textual_coverage_left_in_right": _coverage(left_words, right_words),
        "textual_coverage_right_in_left": _coverage(right_words, left_words),
        "assets": {
            "left": sorted(left_assets),
            "right": sorted(right_assets),
            "common": sorted(left_assets & right_assets),
            "only_left": sorted(left_assets - right_assets),
            "only_right": sorted(right_assets - left_assets),
        },
        "element_kinds": {
            "left": dict(left_kinds),
            "right": dict(right_kinds),
            "only_left": sorted(set(left_kinds) - set(right_kinds)),
            "only_right": sorted(set(right_kinds) - set(left_kinds)),
        },
    }


def _pages_text(pages: Iterable[PageEvidence]) -> str:
    return "\n\n".join(page.text for page in pages)


def _all_elements(pages: Iterable[PageEvidence]) -> Iterable[ElementEvidence]:
    for page in pages:
        yield from page.elements
