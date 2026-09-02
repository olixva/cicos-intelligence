"""Source-aware chunking and safe retrieval profile contracts."""

from dataclasses import replace
from pathlib import Path

import pytest

from domain.models.evidence import ElementEvidence, PageEvidence
from infrastructure.adapters.outbound.document_parser.model_artifacts import ModelBundle

DOCUMENT_HASH = "a" * 64


def _element(
    kind: str,
    text: str,
    section: str | None = None,
    *,
    content_layer: str = "body",
    element_id: str | None = None,
) -> ElementEvidence:
    return ElementEvidence(
        element_id=element_id or f"element-{kind}-{text[:8]}",
        kind=kind,
        text=text,
        section=section,
        content_layer=content_layer,
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


def test_page_101_table_keeps_5475_character_header_table_prefix_and_observations() -> None:
    """The real page-101 text kinds must keep its observation block with the oversize table."""
    from application.services.chunking import chunk_sections

    section = "56. Tabla de Culpabilidad Convenio CIDE (continuación)"
    table_text = "|" + "T" * 5418
    observations = (
        "A2 + B4 = Culpable B, salvo que el A abra la puerta.",
        "B2 + A4 = Culpable A, salvo que el B abra la puerta.",
        "A16 + B0 = Culpable B, salvo que el A circule por vía sin pavimentar.",
        "B16 + A0 = Culpable A, salvo que el B circule por vía sin pavimentar.",
    )
    page = _page(
        "page-101",
        "",
        page_number=101,
        elements=(
            _element("section_header", section, section, element_id="header-101"),
            _element("table", table_text, section, element_id="table-101"),
            _element("text", "(*) OBSERVACIONES:", section, element_id="marker-101"),
            *tuple(
                _element("text", text, section, element_id=f"observation-{index}")
                for index, text in enumerate(observations)
            ),
            _element(
                "page_footer",
                "102",
                section,
                content_layer="furniture",
                element_id="footer-101",
            ),
        ),
    )

    chunks = chunk_sections((page,), max_size=1200)

    table_chunks = tuple(chunk for chunk in chunks if table_text in chunk.text)
    assert len(table_chunks) == 1
    table_chunk = table_chunks[0]
    prefix = f"{section}\n\n{table_text}"
    assert len(prefix) == 5475
    assert table_chunk.text.startswith(prefix)
    assert "(*) OBSERVACIONES:" in table_chunk.text
    assert all(observation in table_chunk.text for observation in observations)
    assert table_chunk.evidence_ids == ("page-101",)
    assert "102" not in "\n".join(chunk.text for chunk in chunks)


def test_structured_table_parts_cross_pages_while_footer_does_not_break_context() -> None:
    """Furniture between same-section table parts must not split their atomic context."""
    from application.services.chunking import chunk_sections

    section = "Matrix continuation"
    pages = (
        _page(
            "page-1",
            "",
            elements=(
                _element("section_header", "Matrix", section),
                _element("table", "part one", section),
                _element("page_footer", "1", section, content_layer="furniture"),
            ),
        ),
        _page(
            "page-2",
            "",
            page_number=2,
            elements=(
                _element("table", "part two", section),
                _element("text", "(*) OBSERVACIÓN:", section),
                _element("text", "Read both parts", section),
            ),
        ),
    )

    chunks = chunk_sections(pages, max_size=8)

    table_chunk = next(chunk for chunk in chunks if "part one" in chunk.text)
    assert table_chunk.text == (
        "Matrix\n\npart one\n\npart two\n\n(*) OBSERVACIÓN:\n\nRead both parts"
    )
    assert table_chunk.evidence_ids == ("page-1", "page-2")
    assert sum("part two" in chunk.text for chunk in chunks) == 1
    assert "\n\n1\n\n" not in table_chunk.text


def test_structured_table_does_not_absorb_observation_block_from_another_section() -> None:
    """A marker-shaped text in another section is not evidence associated with the table."""
    from application.services.chunking import chunk_sections

    page = _page(
        "page-1",
        "",
        elements=(
            _element("section_header", "Section A", "A"),
            _element("table", "table A", "A"),
            _element("note", "Explicit note from section B", "B"),
            _element("text", "OBSERVACIONES:", "B"),
            _element("text", "Note from section B", "B"),
        ),
    )

    chunks = chunk_sections((page,), max_size=100)

    table_chunk = next(chunk for chunk in chunks if "table A" in chunk.text)
    assert table_chunk.text == "Section A\n\ntable A"
    assert "Explicit note from section B" not in table_chunk.text
    assert "Note from section B" not in table_chunk.text


def test_structured_sectionless_table_parts_do_not_cross_source_pages() -> None:
    """Missing section metadata cannot justify associating table parts across pages."""
    from application.services.chunking import chunk_sections

    pages = (
        _page(
            "page-1",
            "",
            elements=(
                _element("section_header", "Unknown matrix", None),
                _element("table", "part one", None),
                _element("page_footer", "1", None, content_layer="furniture"),
            ),
        ),
        _page(
            "page-2",
            "",
            page_number=2,
            elements=(_element("table", "part two", None),),
        ),
    )

    chunks = chunk_sections(pages, max_size=100)

    assert not any("part one" in chunk.text and "part two" in chunk.text for chunk in chunks)


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


def test_committed_profiles_load_to_application_values_and_build_full_signatures(
    fake_model_bundle: ModelBundle,
) -> None:
    """Selectors must resolve to source-specific parser identities before index publication."""
    from application.models.retrieval import (
        FixedChunkingConfig,
        RetrievalProfile,
        SectionChunkingConfig,
    )
    from infrastructure.adapters.outbound.document_parser.docling_parser import DoclingParser
    from infrastructure.adapters.outbound.document_parser.pypdf_parser import PypdfDocumentParser
    from infrastructure.config.profiles import load_profile

    catalog = Path(__file__).parents[1] / "configs"
    baseline = load_profile("baseline", catalog)
    structured = load_profile("structured", catalog)

    assert isinstance(baseline, RetrievalProfile)
    assert isinstance(baseline.chunker, FixedChunkingConfig)
    assert isinstance(structured.chunker, SectionChunkingConfig)

    baseline_parser = PypdfDocumentParser.parser
    structured_parser = DoclingParser(model_bundle=fake_model_bundle).parser
    baseline_signature = baseline.build_index_signature(DOCUMENT_HASH, baseline_parser)
    structured_signature = structured.build_index_signature(DOCUMENT_HASH, structured_parser)

    assert baseline_signature.parser == baseline_parser
    assert structured_signature.parser == structured_parser
    assert '"size"' in baseline_signature.chunker
    assert '"max_size"' in structured_signature.chunker
    assert "observation-block-atomic-v2" in structured_signature.chunker
    assert structured_signature.document_hash == DOCUMENT_HASH
    with pytest.raises(ValueError, match="selector"):
        baseline.build_index_signature(DOCUMENT_HASH, structured_parser)
    with pytest.raises(ValueError, match="selector"):
        structured.build_index_signature(DOCUMENT_HASH, baseline_parser)


@pytest.mark.parametrize(
    "resolved_parser",
    ["pypdf", "pypdfish-6.0", "pypdf-version-unknown", "docling-2.124.0"],
)
def test_profile_rejects_unversioned_deceptive_or_wrong_resolved_parser(
    resolved_parser: str,
) -> None:
    """A selector must bind only its exact versioned parser family."""
    from infrastructure.config.profiles import load_profile

    profile = load_profile("baseline", Path(__file__).parents[1] / "configs")

    with pytest.raises(ValueError, match="selector"):
        profile.build_index_signature(DOCUMENT_HASH, resolved_parser)


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

    linked_catalog = tmp_path / "linked-catalog"
    linked_catalog.symlink_to(catalog, target_is_directory=True)
    with pytest.raises(ProfileCatalogError, match="symlink"):
        load_profile("linked", linked_catalog)


def test_profile_catalog_directory_swap_never_loads_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Replacing the catalog path after its fd opens cannot redirect the profile read."""
    import os

    from infrastructure.config.profiles import ProfileCatalogError, load_profile

    safe_yaml = (
        "parser: pypdf\nchunker: {strategy: fixed, size: 10, overlap: 2}\n"
        "embedding: {model: embedding-test, dimensions: 3}\nlexical_language: spanish\n"
    )
    replacement_yaml = (
        "parser: docling\nchunker: {strategy: fixed, size: 10, overlap: 2}\n"
        "embedding: {model: embedding-test, dimensions: 3}\nlexical_language: spanish\n"
    )
    catalog = tmp_path / "catalog"
    catalog.mkdir()
    (catalog / "baseline.yaml").write_text(safe_yaml)
    replacement = tmp_path / "replacement"
    replacement.mkdir()
    (replacement / "baseline.yaml").write_text(replacement_yaml)
    original = tmp_path / "opened-catalog"
    real_open = os.open
    opened_catalog = False

    def racing_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal opened_catalog
        descriptor = real_open(path, flags, mode, dir_fd=dir_fd)
        if (
            not opened_catalog
            and dir_fd is None
            and Path(os.fsdecode(path)) == catalog
            and flags & os.O_DIRECTORY
        ):
            opened_catalog = True
            catalog.rename(original)
            replacement.rename(catalog)
        return descriptor

    monkeypatch.setattr(os, "open", racing_open)
    loaded = None
    try:
        loaded = load_profile("baseline", catalog)
    except ProfileCatalogError:
        pass

    assert opened_catalog
    assert loaded is None or loaded.parser == "pypdf"


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


# ---------------------------------------------------------------------------
# T3 — extended profile identity (retrieval mode, fusion, reranker, vision,
# ruleset, generator, prompt versions). The index identity must change when
# any of these fields change so cached indexes cannot be reused across
# experiments that alter the candidate pipeline.
# ---------------------------------------------------------------------------


def _minimal_profile_dict(**overrides: object) -> str:
    import yaml

    base = {
        "parser": "pypdf",
        "chunker": {"strategy": "fixed", "size": 100, "overlap": 20},
        "embedding": {"model": "text-embedding-3-small", "dimensions": 1536},
        "lexical_language": "spanish",
    }
    base.update(overrides)
    return yaml.safe_dump(base, sort_keys=False, allow_unicode=True)


def test_profile_identity_changes_with_retrieval_mode(tmp_path: Path) -> None:
    """Switching retrieval mode must produce a different canonical identity."""
    from application.models.retrieval import FixedChunkingConfig, RetrievalProfile
    from infrastructure.config.profiles import load_profile

    (tmp_path / "baseline.yaml").write_text(_minimal_profile_dict(retrieval_mode="dense"))
    (tmp_path / "hybrid.yaml").write_text(_minimal_profile_dict(retrieval_mode="hybrid"))

    dense = load_profile("baseline", tmp_path)
    hybrid = load_profile("hybrid", tmp_path)

    assert dense.retrieval_mode == "dense"
    assert hybrid.retrieval_mode == "hybrid"
    assert dense.identity() != hybrid.identity()


def test_profile_identity_changes_with_reranker_and_prompt_versions(tmp_path: Path) -> None:
    """Prompt version bumps and reranker switches must invalidate the index identity."""
    from infrastructure.config.profiles import load_profile

    (tmp_path / "v1.yaml").write_text(
        _minimal_profile_dict(
            reranker="none", prompt_versions={"document-question": "1"}
        )
    )
    (tmp_path / "v2.yaml").write_text(
        _minimal_profile_dict(
            reranker="openai", prompt_versions={"document-question": "2"}
        )
    )

    first = load_profile("v1", tmp_path)
    second = load_profile("v2", tmp_path)

    assert first.identity() != second.identity()


def test_profile_rejects_unknown_retrieval_mode(tmp_path: Path) -> None:
    """The strict loader must refuse retrieval modes outside the enum."""
    from infrastructure.config.profiles import ProfileCatalogError, load_profile

    (tmp_path / "bad.yaml").write_text(_minimal_profile_dict(retrieval_mode="sparse"))
    with pytest.raises(ProfileCatalogError):
        load_profile("bad", tmp_path)


def test_profile_defaults_keep_backward_compatibility(tmp_path: Path) -> None:
    """Profiles without extended fields must keep the previous defaults."""
    from infrastructure.config.profiles import load_profile

    (tmp_path / "legacy.yaml").write_text(_minimal_profile_dict())
    profile = load_profile("legacy", tmp_path)
    assert profile.retrieval_mode == "hybrid"
    assert profile.fusion == "rrf"
    assert profile.reranker == "none"
    assert profile.vision == "none"
    assert profile.ruleset == "audit-required"
    assert profile.generator == "openai-responses"
    assert profile.prompt_versions is None
