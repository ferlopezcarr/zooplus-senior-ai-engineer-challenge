from __future__ import annotations

import json
from urllib.error import HTTPError

import pytest

from src.infrastructure.output.embedding_client import (
    OpenAICompatibleEmbeddingClient,
    build_embeddings_url,
)
from src.infrastructure.output.model.error import EmbeddingProviderHttpError


def test_build_embeddings_url_rejects_non_https_url() -> None:
    with pytest.raises(ValueError, match="EMBEDDING_BASE_URL"):
        build_embeddings_url("http://embeddings.example.test/v1")


def test_embed_raises_safe_error_for_http_failure(monkeypatch) -> None:
    client = OpenAICompatibleEmbeddingClient(
        api_key="secret",
        model="test-model",
        base_url="https://embeddings.example.test/v1",
    )

    def _raise_http_error(request, timeout):
        raise HTTPError(
            request.full_url,
            500,
            "boom",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(
        "src.infrastructure.output.embedding_client.urlopen", _raise_http_error
    )

    with pytest.raises(
        EmbeddingProviderHttpError, match="Embedding provider request failed"
    ):
        client.embed("hello")


def test_embed_raises_safe_error_for_malformed_body(monkeypatch) -> None:
    client = OpenAICompatibleEmbeddingClient(
        api_key="secret",
        model="test-model",
        base_url="https://embeddings.example.test/v1",
    )

    class StubResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps({"data": [{"oops": []}]}).encode("utf-8")

    monkeypatch.setattr(
        "src.infrastructure.output.embedding_client.urlopen",
        lambda request, timeout: StubResponse(),
    )

    with pytest.raises(
        EmbeddingProviderHttpError, match="Embedding provider request failed"
    ):
        client.embed("hello")
