"""Strict YAML retrieval profiles loaded only from a local catalog."""

import re
from collections.abc import Callable
from dataclasses import fields
from pathlib import Path
from typing import Annotated, Literal, Self, cast

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode

from application.models.retrieval import (
    FixedChunkingConfig,
    IndexSignature,
    RetrievalProfile,
    SectionChunkingConfig,
)

_PROFILE_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


class ProfileCatalogError(ValueError):
    """Raised when a profile key or document is unsafe or invalid."""


class _UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that refuses silent duplicate-key replacement."""


def _construct_unique_mapping(
    loader: _UniqueKeyLoader, node: MappingNode, deep: bool = False
) -> dict[object, object]:
    loader.flatten_mapping(node)
    mapping: dict[object, object] = {}
    construct_object = cast(
        Callable[[object, bool], object],
        loader.construct_object,  # pyright: ignore[reportUnknownMemberType]
    )
    for key_node, value_node in node.value:
        key = construct_object(key_node, deep)
        try:
            duplicate = key in mapping
        except TypeError as exc:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found an unhashable mapping key",
                key_node.start_mark,
            ) from exc
        if duplicate:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found duplicate mapping key",
                key_node.start_mark,
            )
        mapping[key] = construct_object(value_node, deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class _FixedChunkerDocument(_StrictModel):
    strategy: Literal["fixed"]
    size: int = Field(gt=0)
    overlap: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_overlap(self) -> Self:
        if self.overlap >= self.size:
            raise ValueError("overlap must be smaller than size")
        return self


class _SectionChunkerDocument(_StrictModel):
    strategy: Literal["sections"]
    max_size: int = Field(gt=0)


type _ChunkerDocument = Annotated[
    _FixedChunkerDocument | _SectionChunkerDocument,
    Field(discriminator="strategy"),
]


class _EmbeddingDocument(_StrictModel):
    model: str
    dimensions: int = Field(gt=0)

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("model must be nonempty")
        return value


class _ProfileDocument(_StrictModel):
    parser: Literal["pypdf", "docling"]
    chunker: _ChunkerDocument
    embedding: _EmbeddingDocument
    lexical_language: str

    @field_validator("lexical_language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("lexical_language must be nonempty")
        return value

    @model_validator(mode="after")
    def validate_parser_chunker_pair(self) -> Self:
        if isinstance(self.chunker, _SectionChunkerDocument) and self.parser != "docling":
            raise ValueError("sections chunking requires the docling parser")
        return self

    def to_application(self) -> RetrievalProfile:
        chunker: FixedChunkingConfig | SectionChunkingConfig
        if isinstance(self.chunker, _FixedChunkerDocument):
            chunker = FixedChunkingConfig(self.chunker.size, self.chunker.overlap)
        else:
            chunker = SectionChunkingConfig(self.chunker.max_size)
        return RetrievalProfile(
            parser=self.parser,
            chunker=chunker,
            embedding_model=self.embedding.model,
            dimensions=self.embedding.dimensions,
            lexical_language=self.lexical_language,
        )


def load_profile(name: str, catalog_dir: Path) -> RetrievalProfile:
    """Load one strict ``<name>.yaml`` document without accepting a caller path."""

    if _PROFILE_KEY.fullmatch(name) is None:
        raise ProfileCatalogError("profile name must be a safe catalog key")
    if catalog_dir.is_symlink():
        raise ProfileCatalogError("profile catalog must not be a symlink")
    try:
        catalog = catalog_dir.resolve(strict=True)
    except OSError as exc:
        raise ProfileCatalogError("profile catalog is unavailable") from exc
    if not catalog.is_dir():
        raise ProfileCatalogError("profile catalog is not a directory")

    candidate = catalog / f"{name}.yaml"
    if candidate.is_symlink():
        raise ProfileCatalogError("profile document must not be a symlink")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise ProfileCatalogError(f"unknown profile: {name}") from exc
    if resolved.parent != catalog or not resolved.is_file():
        raise ProfileCatalogError("profile document is outside the catalog")

    try:
        raw = yaml.load(resolved.read_text(), Loader=_UniqueKeyLoader)
        if not isinstance(raw, dict):
            raise ProfileCatalogError("profile YAML must be a mapping")
        document = _ProfileDocument.model_validate(cast(dict[object, object], raw))
    except ProfileCatalogError:
        raise
    except (OSError, yaml.YAMLError, ValidationError, ValueError) as exc:
        raise ProfileCatalogError(f"invalid profile: {name}") from exc
    return document.to_application()


def serialize_index_signature(signature: IndexSignature) -> dict[str, str | int]:
    """Serialize every signature field for an index manifest."""

    return {
        field.name: cast(str | int, getattr(signature, field.name))
        for field in fields(IndexSignature)
    }
