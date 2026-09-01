"""Source-aware chunking and safe retrieval profile contracts."""

from dataclasses import replace
from pathlib import Path

import pytest

from domain.models.evidence import ElementEvidence, PageEvidence

DOCUMENT_HASH = "a" * 64


def _element(kind: str, text: str, section: str | None = None) -> ElementEvidence:
    return ElementEvidence(
        element_id=f"element-{kind}-{text[:8]}",
        kind=kind,
        text=text,
        section=section,
        content_layer="body",
        regions=(),
    )


def _page(
    evidence_id: str,
    text: str,
    *,
    page_number: int = 1,
    elements: tuple[ElementEvidence, ...] = (),
) -> PageEvidence:
    return PageEvidence(
        evidence_id=evidence_id,
        document_hash=DOCUMENT_HASH,
        pdf_page=page_number,
        text=text,
        printed_label=None,
        image_path=None,
        regions=(),
        elements=elements,
    )


@pytest.mark.parametrize("changed_field", ["dimensions", "lexical_language"])
def test_index_signature_change_invalidates_index(changed_field: str) -> None:
    """Ignoring vector or lexical changes would reuse an incompatible index."""
    from application.models.retrieval import (
        IncompatibleIndexError,
        IndexSignature,
        assert_compatible,
    )

    original = IndexSignature(
        DOCUMENT_HASH,
        "pypdf-6.1.0",
        "fixed",
        "embedding-test",
        3,
        "spanish",
    )
    changed = replace(
        original,
        **({"dimensions": 4} if changed_field == "dimensions" else {"lexical_language": "english"}),
    )

    with pytest.raises(IncompatibleIndexError, match=changed_field):
        assert_compatible(original, changed)


def test_index_compatibility_compares_every_field_and_serializes_all_fields() -> None:
    """A partial name-based comparison or manifest would hide an incompatible publication."""
    from application.models.retrieval import IndexSignature, assert_compatible
    from infrastructure.config.profiles import serialize_index_signature

    signature = IndexSignature(
        DOCUMENT_HASH,
        "docling-2.124.0-bundle-deadbeef",
        '{"max_size":1200,"strategy":"sections"}',
        "embedding-test",
        3,
        "spanish",
    )
    assert_compatible(signature, signature)
    assert serialize_index_signature(signature) == {
        "document_hash": DOCUMENT_HASH,
        "parser": "docling-2.124.0-bundle-deadbeef",
        "chunker": '{"max_size":1200,"strategy":"sections"}',
        "embedding_model": "embedding-test",
        "dimensions": 3,
        "lexical_language": "spanish",
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("document_hash", "not-a-sha256"),
        ("parser", ""),
        ("chunker", " "),
        ("embedding_model", ""),
        ("dimensions", 0),
        ("lexical_language", ""),
    ],
)
def test_index_signature_rejects_incomplete_identity(field: str, value: object) -> None:
    """An incomplete signature must not be accepted as an index compatibility boundary."""
    from application.models.retrieval import IndexSignature

    values: dict[str, object] = {
        "document_hash": DOCUMENT_HASH,
        "parser": "pypdf-6.1.0",
        "chunker": "fixed",
        "embedding_model": "embedding-test",
        "dimensions": 3,
        "lexical_language": "spanish",
    }
    values[field] = value
    with pytest.raises(ValueError):
        IndexSignature(**values)  # pyright: ignore[reportArgumentType]


@pytest.mark.parametrize(
    ("size", "overlap"),
    [(0, 0), (-1, 0), (4, -1), (4, 4), (4, 5)],
)
def test_fixed_chunking_rejects_invalid_window(size: int, overlap: int) -> None:
    """Invalid windows must fail instead of looping or silently dropping characters."""
    from application.services.chunking import chunk_fixed

    with pytest.raises(ValueError):
        chunk_fixed((_page("page-1", "abcdef"),), size=size, overlap=overlap)


def test_fixed_chunks_cross_pages_with_ordered_source_evidence_and_skip_blanks() -> None:
    """Cross-page cuts must cite every page that actually supplied characters."""
    from application.services.chunking import chunk_fixed

    pages = (
        _page("page-1", "abcd", page_number=1),
        _page("page-blank", "", page_number=2),
        _page("page-3", "efgh", page_number=3),
    )

    chunks = chunk_fixed(pages, size=6, overlap=2)

    assert tuple((chunk.text, chunk.evidence_ids) for chunk in chunks) == (
        ("abcdef", ("page-1", "page-3")),
        ("efgh", ("page-3",)),
    )


def test_fixed_chunk_ids_are_stable_and_bind_sources_and_all_parameters() -> None:
    """Dropping evidence or an effective window parameter from the hash would collide."""
    from application.services.chunking import chunk_fixed

    page = _page("page-1", "same text")
    identical = chunk_fixed((page,), size=20, overlap=0)[0]
    repeated = chunk_fixed((page,), size=20, overlap=0)[0]
    other_source = chunk_fixed((_page("page-2", "same text"),), size=20, overlap=0)[0]
    other_size = chunk_fixed((page,), size=21, overlap=0)[0]
    other_overlap = chunk_fixed((page,), size=20, overlap=1)[0]

    assert identical.chunk_id == repeated.chunk_id
    assert len(identical.chunk_id) == 64
    assert (
        len(
            {
                identical.chunk_id,
                other_source.chunk_id,
                other_size.chunk_id,
                other_overlap.chunk_id,
            }
        )
        == 4
    )


def test_structured_table_header_and_immediate_note_form_one_oversize_chunk() -> None:
    """Splitting an oversize table from its labels or note would destroy its context."""
    from application.services.chunking import chunk_sections

    pages = (
        _page(
            "page-1",
            "",
            elements=(
                _element("text", "Before"),
                _element("section_header", "CIDE matrix", "Matrix"),
                _element("table", "A | B\n1 | 2", "Matrix"),
            ),
        ),
        _page(
            "page-2",
            "",
            page_number=2,
            elements=(
                _element("footnote", "Note: read both axes", "Matrix"),
                _element("text", "After", "Matrix"),
            ),
        ),
    )

    chunks = chunk_sections(pages, max_size=12)

    table_chunk = next(chunk for chunk in chunks if "A | B" in chunk.text)
    assert table_chunk.text == "CIDE matrix\n\nA | B\n1 | 2\n\nNote: read both axes"
    assert table_chunk.evidence_ids == ("page-1", "page-2")
    assert len(table_chunk.text) > 12
    assert all("CIDE matrix" not in chunk.text for chunk in chunks if chunk is not table_chunk)
    assert all(
        "Note: read both axes" not in chunk.text for chunk in chunks if chunk is not table_chunk
    )


def test_structured_normal_text_splits_deterministically_and_binds_policy() -> None:
    """Normal oversize text may split, while IDs must bind the configured section policy."""
    from application.services.chunking import chunk_sections

    page = _page("page-1", "abcdefghij")
    chunks = chunk_sections((page,), max_size=4)
    repeated = chunk_sections((page,), max_size=4)
    other_limit = chunk_sections((page,), max_size=5)

    assert tuple(chunk.text for chunk in chunks) == ("abcd", "efgh", "ij")
    assert chunks == repeated
    assert chunks[0].chunk_id != other_limit[0].chunk_id
    assert all(chunk.evidence_ids == ("page-1",) for chunk in chunks)


@pytest.mark.parametrize("max_size", [0, -1])
def test_structured_chunking_rejects_invalid_limit(max_size: int) -> None:
    """A non-positive structured limit cannot define deterministic packing."""
    from application.services.chunking import chunk_sections

    with pytest.raises(ValueError):
        chunk_sections((_page("page-1", "text"),), max_size=max_size)


def test_committed_profiles_load_to_application_values_and_build_full_signatures() -> None:
    """Selectors must resolve to source-specific parser identities before index publication."""
    from application.models.retrieval import (
        FixedChunkingConfig,
        RetrievalProfile,
        SectionChunkingConfig,
    )
    from infrastructure.config.profiles import load_profile

    catalog = Path(__file__).parents[1] / "configs"
    baseline = load_profile("baseline", catalog)
    structured = load_profile("structured", catalog)

    assert isinstance(baseline, RetrievalProfile)
    assert isinstance(baseline.chunker, FixedChunkingConfig)
    assert isinstance(structured.chunker, SectionChunkingConfig)

    baseline_signature = baseline.build_index_signature(DOCUMENT_HASH, "pypdf-6.1.0")
    structured_parser = "docling-2.124.0-pdfium-5.13.0-bundle-135374b2"
    structured_signature = structured.build_index_signature(DOCUMENT_HASH, structured_parser)

    assert baseline_signature.parser == "pypdf-6.1.0"
    assert structured_signature.parser == structured_parser
    assert '"size"' in baseline_signature.chunker
    assert '"max_size"' in structured_signature.chunker
    assert structured_signature.document_hash == DOCUMENT_HASH


@pytest.mark.parametrize("name", ["../baseline", "nested/profile", "baseline.yaml", ".", ""])
def test_profile_catalog_rejects_non_key_paths(tmp_path: Path, name: str) -> None:
    """Treating a profile name as a path would expose arbitrary local YAML."""
    from infrastructure.config.profiles import ProfileCatalogError, load_profile

    with pytest.raises(ProfileCatalogError):
        load_profile(name, tmp_path)


def test_profile_catalog_rejects_symlinks(tmp_path: Path) -> None:
    """A catalog symlink must not redirect profile reads across the trust boundary."""
    from infrastructure.config.profiles import ProfileCatalogError, load_profile

    outside = tmp_path / "outside.yaml"
    outside.write_text(
        "parser: pypdf\nchunker: {strategy: fixed, size: 10, overlap: 2}\n"
        "embedding: {model: embedding-test, dimensions: 3}\nlexical_language: spanish\n"
    )
    catalog = tmp_path / "catalog"
    catalog.mkdir()
    (catalog / "linked.yaml").symlink_to(outside)

    with pytest.raises(ProfileCatalogError, match="symlink"):
        load_profile("linked", catalog)


@pytest.mark.parametrize(
    "yaml_text",
    [
        "- not\n- a\n- mapping\n",
        (
            "parser: pypdf\nchunker: {strategy: fixed, size: 10, overlap: 2}\n"
            "embedding: {model: embedding-test, dimensions: 3}\nlexical_language: spanish\n"
            "unknown: rejected\n"
        ),
        (
            "parser: pypdf\nparser: docling\n"
            "chunker: {strategy: fixed, size: 10, overlap: 2}\n"
            "embedding: {model: embedding-test, dimensions: 3}\nlexical_language: spanish\n"
        ),
        (
            "parser: pypdf\n"
            "chunker: {strategy: fixed, size: 10, overlap: 2, max_size: 20}\n"
            "embedding: {model: embedding-test, dimensions: 3}\nlexical_language: spanish\n"
        ),
        (
            "parser: pypdf\nchunker: {strategy: sections, max_size: 20}\n"
            "embedding: {model: embedding-test, dimensions: 3}\nlexical_language: spanish\n"
        ),
    ],
)
def test_profile_schema_rejects_non_mapping_unknown_duplicate_or_incompatible_yaml(
    tmp_path: Path, yaml_text: str
) -> None:
    """Ambiguous or impossible profiles must fail before they can name an index."""
    from infrastructure.config.profiles import ProfileCatalogError, load_profile

    (tmp_path / "invalid.yaml").write_text(yaml_text)

    with pytest.raises(ProfileCatalogError):
        load_profile("invalid", tmp_path)
