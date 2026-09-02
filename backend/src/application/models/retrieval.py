"""Immutable retrieval values shared by ingestion and index adapters."""

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, fields
from typing import Literal

_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")

# Literal types kept narrow and version-bounded so profiles are reproducible.
RetrievalMode = Literal["dense", "bm25", "hybrid"]
FusionStrategy = Literal["rrf"]
RerankerKind = Literal["none", "openai"]
VisionKind = Literal["none", "openai-responses"]
RulesetKind = Literal["audit-required", "inline-v1"]
GeneratorKind = Literal["openai-responses"]


class IncompatibleIndexError(ValueError):
    """Raised when an existing index does not match the requested signature."""


@dataclass(frozen=True, slots=True)
class Chunk:
    """Derived retrieval text with stable links back to source-page evidence."""

    chunk_id: str
    text: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IndexSignature:
    """Every content or processing identity that determines index compatibility."""

    document_hash: str
    parser: str
    chunker: str
    embedding_model: str
    dimensions: int
    lexical_language: str

    def __post_init__(self) -> None:
        if _SHA256_PATTERN.fullmatch(self.document_hash) is None:
            raise ValueError("document_hash must be a lowercase SHA-256 digest")
        for name in ("parser", "chunker", "embedding_model", "lexical_language"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be nonempty")
        _require_positive_int("dimensions", self.dimensions)


def assert_compatible(actual: IndexSignature, expected: IndexSignature) -> None:
    """Require structural equality and name only the incompatible fields."""

    different = tuple(
        field.name
        for field in fields(IndexSignature)
        if getattr(actual, field.name) != getattr(expected, field.name)
    )
    if different:
        raise IncompatibleIndexError(f"Incompatible index signature fields: {', '.join(different)}")


@dataclass(frozen=True, slots=True)
class FixedChunkingConfig:
    """Effective fixed character-window configuration."""

    size: int
    overlap: int
    strategy: Literal["fixed"] = "fixed"

    def __post_init__(self) -> None:
        _require_positive_int("size", self.size)
        _require_nonnegative_int("overlap", self.overlap)
        if not 0 <= self.overlap < self.size:
            raise ValueError("overlap must satisfy 0 <= overlap < size")

    def identity(self) -> str:
        """Return the complete canonical chunker identity stored in index signatures."""

        return _canonical_json(
            {
                "overlap": self.overlap,
                "page_join": "",
                "policy": "character-window-v1",
                "size": self.size,
                "strategy": self.strategy,
            }
        )


@dataclass(frozen=True, slots=True)
class SectionChunkingConfig:
    """Effective structure-aware configuration with conservative table grouping."""

    max_size: int
    strategy: Literal["sections"] = "sections"

    def __post_init__(self) -> None:
        _require_positive_int("max_size", self.max_size)

    def identity(self) -> str:
        """Return the complete canonical chunker identity stored in index signatures."""

        return _canonical_json(
            {
                "max_size": self.max_size,
                "policy": "ordered-section-tables-observation-block-atomic-v2",
                "separator": "\n\n",
                "strategy": self.strategy,
            }
        )


type ChunkingConfig = FixedChunkingConfig | SectionChunkingConfig


@dataclass(frozen=True, slots=True)
class RetrievalProfile:
    """Validated application value produced from an infrastructure profile document.

    The profile identity binds parser, chunking, embedding, retrieval mode,
    fusion, reranker, vision, ruleset, generator and prompt versions. Any
    change to one of these fields must produce a different index signature
    so cached indexes can never be reused across prompt or model changes.
    """

    parser: Literal["pypdf", "docling"]
    chunker: ChunkingConfig
    embedding_model: str
    dimensions: int
    lexical_language: str
    retrieval_mode: RetrievalMode = "hybrid"
    fusion: FusionStrategy = "rrf"
    reranker: RerankerKind = "none"
    vision: VisionKind = "none"
    ruleset: RulesetKind = "audit-required"
    generator: GeneratorKind = "openai-responses"
    prompt_versions: Mapping[str, str] | None = None

    def __post_init__(self) -> None:
        if self.parser not in ("pypdf", "docling"):
            raise ValueError("parser must be pypdf or docling")
        if isinstance(self.chunker, SectionChunkingConfig) and self.parser != "docling":
            raise ValueError("sections chunking requires the docling parser")
        if not self.embedding_model.strip():
            raise ValueError("embedding_model must be nonempty")
        _require_positive_int("dimensions", self.dimensions)
        if not self.lexical_language.strip():
            raise ValueError("lexical_language must be nonempty")
        if self.prompt_versions is not None:
            for key, value in self.prompt_versions.items():
                if not key.strip() or not value.strip():
                    raise ValueError("prompt_versions keys and values must be nonempty")

    def build_index_signature(self, document_hash: str, resolved_parser: str) -> IndexSignature:
        """Bind selectors to the exact source and parser identity used for indexing."""

        if re.fullmatch(rf"{re.escape(self.parser)}-[0-9]\S*", resolved_parser) is None:
            raise ValueError("resolved_parser does not match the versioned parser selector")
        return IndexSignature(
            document_hash=document_hash,
            parser=resolved_parser,
            chunker=self.chunker.identity(),
            embedding_model=self.embedding_model,
            dimensions=self.dimensions,
            lexical_language=self.lexical_language,
        )

    def identity(self) -> str:
        """Return a canonical JSON identity covering every retrieval-affecting field."""

        return _canonical_json(
            {
                "parser": self.parser,
                "chunker": self.chunker.identity(),
                "embedding_model": self.embedding_model,
                "dimensions": self.dimensions,
                "lexical_language": self.lexical_language,
                "retrieval_mode": self.retrieval_mode,
                "fusion": self.fusion,
                "reranker": self.reranker,
                "vision": self.vision,
                "ruleset": self.ruleset,
                "generator": self.generator,
                "prompt_versions": dict(self.prompt_versions or {}),
            }
        )


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _require_positive_int(name: str, value: object) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _require_nonnegative_int(name: str, value: object) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
