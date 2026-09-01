"""Shared lightweight dependencies for unit tests."""

from pathlib import Path

import pytest

from infrastructure.adapters.outbound.document_parser.model_artifacts import ModelBundle


@pytest.fixture
def fake_model_bundle(tmp_path: Path) -> ModelBundle:
    """Provide path-shaped pins without loading neural weights in unit tests."""
    from infrastructure.adapters.outbound.document_parser.model_artifacts import (
        PINNED_MODEL_MANIFEST,
    )

    return ModelBundle(tmp_path / "fake-model-bundle", PINNED_MODEL_MANIFEST)
