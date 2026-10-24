"""Tests for local server health provenance derived from Qdrant."""

from __future__ import annotations

import json
from typing import Any


def test_qdrant_identity_uses_shared_endpoint_and_signed_active_index(
    monkeypatch: Any,
) -> None:
    import asgi_local

    signature: dict[str, Any] = {
        "document_hash": "b" * 64,
        "parser": "pypdf-6.16.2",
        "chunker": "fixed-1200-120",
        "embedding_model": "text-embedding-3-small",
        "dimensions": 1536,
        "lexical_language": "spanish",
    }
    responses = iter(
        (
            {
                "result": {
                    "aliases": [
                        {
                            "alias_name": "allianz-manual-active",
                            "collection_name": "allianz-manual-build-1",
                        }
                    ]
                }
            },
            {
                "result": {
                    "points_count": 118,
                    "config": {"metadata": {"index_signature": signature}},
                }
            },
        )
    )
    requested_urls: list[str] = []

    class _Response:
        def __init__(self, body: dict[str, Any]) -> None:
            self.body = body

        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(self.body).encode()

    def fake_urlopen(url: str, *, timeout: int) -> _Response:
        assert timeout == 2
        requested_urls.append(url)
        return _Response(next(responses))

    monkeypatch.setenv("QDRANT_URL", "http://qdrant-query:6333")
    monkeypatch.setenv("ALLIANZ_QDRANT_URL", "http://qdrant-ingestion:6333")
    monkeypatch.setattr(asgi_local.urllib.request, "urlopen", fake_urlopen)

    identity = asgi_local._qdrant_active_index_identity()

    assert identity is not None
    assert identity["alias_name"] == "allianz-manual-active"
    assert identity["collection_name"] == "allianz-manual-build-1"
    assert identity["points_count"] == 118
    assert identity["index_signature"]["document_hash"] == "b" * 64
    assert requested_urls == [
        "http://qdrant-query:6333/aliases",
        "http://qdrant-query:6333/collections/allianz-manual-build-1",
    ]
