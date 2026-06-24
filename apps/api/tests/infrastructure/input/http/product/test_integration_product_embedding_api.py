from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import main


TEST_DATABASE_URL = (
    "postgresql+psycopg://test_user:test_password@example.test:5432/catalog"
)
ARTICLE_ID = 5511354
INTERNAL_API_TOKEN = "internal-maintenance-token"
EMBEDDING_ROUTE = f"/internal/products/{ARTICLE_ID}/embedding"


def _patch_database_retriever(monkeypatch) -> None:
    class StubDatabaseProductRetriever:
        def __init__(
            self,
            database_url: str,
            embedding_client_factory=None,
        ) -> None:
            assert database_url == TEST_DATABASE_URL

        def readiness_error(self) -> str | None:
            return None

        def retrieve(self, chat, limit: int = 3):
            return []

    monkeypatch.setattr(main, "DatabaseProductRetriever", StubDatabaseProductRetriever)


def _patch_embedding_store(monkeypatch, *, entry):
    state = {"saved_article_id": None, "saved_embedding": None}

    class StubEmbeddingStore:
        def __init__(self, database_url: str) -> None:
            assert database_url == TEST_DATABASE_URL

        def get_entry(self, article_id: int):
            if entry is None:
                return None

            assert article_id == entry.article_id
            return entry

        def save_embedding(self, article_id: int, embedding: list[float]) -> None:
            state["saved_article_id"] = article_id
            state["saved_embedding"] = embedding

    monkeypatch.setattr(main, "DatabaseProductEmbeddingStore", StubEmbeddingStore)
    return state


def _patch_embedding_client(monkeypatch, client_class) -> None:
    monkeypatch.setenv(
        "EMBEDDING_BASE_URL", "https://embeddings.example.test/v1/embeddings"
    )
    monkeypatch.setenv("EMBEDDING_API_KEY", "super-secret-api-key")
    monkeypatch.setenv("EMBEDDING_MODEL", "test-embedding-model")
    monkeypatch.setattr(main, "OpenAICompatibleEmbeddingClient", client_class)


def _build_auth_headers(token: str = INTERNAL_API_TOKEN) -> dict[str, str]:
    return {"X-Internal-Token": token}


def _entry(*, has_embedding: bool):
    from src.features.product.application.ports import ProductEmbeddingEntry

    return ProductEmbeddingEntry(
        article_id=ARTICLE_ID,
        embedding_document="Dog food for sensitive digestion.",
        has_embedding=has_embedding,
    )


def setup_function() -> None:
    main._missing_llm_config_warnings_emitted = set()
    main._embedding_retrieval_warnings_emitted = set()


def _build_test_client(monkeypatch) -> TestClient:
    monkeypatch.setattr(main, "DOTENV_PATH", Path(".missing-test.env"))
    monkeypatch.setenv("PRODUCT_CATALOG_DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("INTERNAL_API_TOKEN", INTERNAL_API_TOKEN)
    _patch_database_retriever(monkeypatch)
    return TestClient(main.build_app())


def test_product_embedding_endpoint_returns_404_when_product_is_missing(
    monkeypatch,
) -> None:
    _patch_embedding_store(monkeypatch, entry=None)

    client = _build_test_client(monkeypatch)
    response = client.post(EMBEDDING_ROUTE, headers=_build_auth_headers())

    assert response.status_code == 404
    assert response.json() == {"detail": "Product not found."}


def test_product_embedding_endpoint_skips_provider_when_embedding_exists(
    monkeypatch,
) -> None:
    calls = {"count": 0}

    class StubEmbeddingClient:
        def __init__(self, **kwargs) -> None:
            calls["count"] += 1

        def embed(self, text: str) -> list[float]:
            raise AssertionError("provider should not be called")

    saved_state = _patch_embedding_store(monkeypatch, entry=_entry(has_embedding=True))
    _patch_embedding_client(monkeypatch, StubEmbeddingClient)

    client = _build_test_client(monkeypatch)
    response = client.post(EMBEDDING_ROUTE, headers=_build_auth_headers())

    assert response.status_code == 200
    assert response.json() == {
        "article_id": ARTICLE_ID,
        "status": "already_embedded",
        "model": None,
        "dimensions": None,
    }
    assert calls["count"] == 0
    assert saved_state == {"saved_article_id": None, "saved_embedding": None}


def test_product_embedding_endpoint_generates_and_persists_missing_embedding(
    monkeypatch,
) -> None:
    captured = {"document": None}

    class StubEmbeddingClient:
        def __init__(
            self,
            api_key: str,
            model: str,
            base_url: str,
            timeout_seconds: float,
        ) -> None:
            assert api_key == "super-secret-api-key"
            assert model == "test-embedding-model"
            assert base_url == "https://embeddings.example.test/v1/embeddings"
            assert timeout_seconds == 10.0
            self.model = model

        def embed(self, text: str) -> list[float]:
            captured["document"] = text
            return [0.1, 0.2, 0.3]

    saved_state = _patch_embedding_store(monkeypatch, entry=_entry(has_embedding=False))
    _patch_embedding_client(monkeypatch, StubEmbeddingClient)

    client = _build_test_client(monkeypatch)
    response = client.post(EMBEDDING_ROUTE, headers=_build_auth_headers())

    assert response.status_code == 200
    assert response.json() == {
        "article_id": ARTICLE_ID,
        "status": "embedded",
        "model": "test-embedding-model",
        "dimensions": 3,
    }
    assert captured["document"] == "Dog food for sensitive digestion."
    assert saved_state == {
        "saved_article_id": ARTICLE_ID,
        "saved_embedding": [0.1, 0.2, 0.3],
    }


def test_product_embedding_endpoint_recalculates_when_force_is_true(
    monkeypatch,
) -> None:
    calls = {"count": 0}

    class StubEmbeddingClient:
        def __init__(self, **kwargs) -> None:
            self.model = "test-embedding-model"

        def embed(self, text: str) -> list[float]:
            calls["count"] += 1
            return [0.9, 0.8]

    saved_state = _patch_embedding_store(monkeypatch, entry=_entry(has_embedding=True))
    _patch_embedding_client(monkeypatch, StubEmbeddingClient)

    client = _build_test_client(monkeypatch)
    response = client.post(
        f"{EMBEDDING_ROUTE}?force=true",
        headers=_build_auth_headers(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "article_id": ARTICLE_ID,
        "status": "recalculated",
        "model": "test-embedding-model",
        "dimensions": 2,
    }
    assert calls["count"] == 1
    assert saved_state == {
        "saved_article_id": ARTICLE_ID,
        "saved_embedding": [0.9, 0.8],
    }


def test_product_embedding_endpoint_returns_safe_error_when_config_is_missing(
    monkeypatch,
) -> None:
    _patch_embedding_store(monkeypatch, entry=_entry(has_embedding=False))
    monkeypatch.delenv("EMBEDDING_BASE_URL", raising=False)
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)

    client = _build_test_client(monkeypatch)
    response = client.post(EMBEDDING_ROUTE, headers=_build_auth_headers())

    assert response.status_code == 503
    assert response.json() == {"detail": "Embedding generation is unavailable."}


def test_product_embedding_endpoint_hides_provider_secrets_on_failure(
    monkeypatch,
) -> None:
    class StubEmbeddingClient:
        def __init__(self, **kwargs) -> None:
            pass

        def embed(self, text: str) -> list[float]:
            raise RuntimeError(
                "provider exploded for super-secret-api-key with vector [0.1, 0.2]"
            )

    saved_state = _patch_embedding_store(monkeypatch, entry=_entry(has_embedding=False))
    _patch_embedding_client(monkeypatch, StubEmbeddingClient)

    client = _build_test_client(monkeypatch)
    response = client.post(EMBEDDING_ROUTE, headers=_build_auth_headers())

    assert response.status_code == 502
    assert response.json() == {"detail": "Embedding provider request failed."}
    assert "super-secret-api-key" not in response.text
    assert "[0.1, 0.2]" not in response.text
    assert saved_state == {"saved_article_id": None, "saved_embedding": None}


def test_product_embedding_endpoint_is_unavailable_without_internal_token_config(
    monkeypatch,
) -> None:
    monkeypatch.setattr(main, "DOTENV_PATH", Path(".missing-test.env"))
    monkeypatch.setenv("PRODUCT_CATALOG_DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.delenv("INTERNAL_API_TOKEN", raising=False)
    _patch_database_retriever(monkeypatch)
    _patch_embedding_store(monkeypatch, entry=_entry(has_embedding=False))

    client = TestClient(main.build_app())
    response = client.post(EMBEDDING_ROUTE)

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Product embedding maintenance is unavailable."
    }


def test_product_embedding_endpoint_requires_internal_token_header(monkeypatch) -> None:
    _patch_embedding_store(monkeypatch, entry=_entry(has_embedding=False))

    client = _build_test_client(monkeypatch)
    response = client.post(EMBEDDING_ROUTE)

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authorized."}


def test_product_embedding_endpoint_rejects_wrong_internal_token(monkeypatch) -> None:
    _patch_embedding_store(monkeypatch, entry=_entry(has_embedding=False))

    client = _build_test_client(monkeypatch)
    response = client.post(
        EMBEDDING_ROUTE,
        headers=_build_auth_headers("wrong-token"),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Not authorized."}


def test_product_embedding_endpoint_returns_unavailable_for_invalid_base_url(
    monkeypatch,
) -> None:
    _patch_embedding_store(monkeypatch, entry=_entry(has_embedding=False))
    monkeypatch.setenv(
        "EMBEDDING_BASE_URL", "https://embeddings.example.test/v1/embeddings?extra=1"
    )
    monkeypatch.setenv("EMBEDDING_API_KEY", "super-secret-api-key")
    monkeypatch.setenv("EMBEDDING_MODEL", "test-embedding-model")

    client = _build_test_client(monkeypatch)
    response = client.post(EMBEDDING_ROUTE, headers=_build_auth_headers())

    assert response.status_code == 503
    assert response.json() == {"detail": "Embedding generation is unavailable."}


def test_product_embedding_endpoint_returns_unavailable_for_invalid_timeout(
    monkeypatch,
) -> None:
    _patch_embedding_store(monkeypatch, entry=_entry(has_embedding=False))
    monkeypatch.setenv(
        "EMBEDDING_BASE_URL", "https://embeddings.example.test/v1/embeddings"
    )
    monkeypatch.setenv("EMBEDDING_API_KEY", "super-secret-api-key")
    monkeypatch.setenv("EMBEDDING_MODEL", "test-embedding-model")
    monkeypatch.setenv("EMBEDDING_TIMEOUT_SECONDS", "invalid")

    client = _build_test_client(monkeypatch)
    response = client.post(EMBEDDING_ROUTE, headers=_build_auth_headers())

    assert response.status_code == 503
    assert response.json() == {"detail": "Embedding generation is unavailable."}


def test_product_embedding_endpoint_returns_404_when_row_disappears_on_save(
    monkeypatch,
) -> None:
    class StubEmbeddingStore:
        def __init__(self, database_url: str) -> None:
            assert database_url == TEST_DATABASE_URL

        def get_entry(self, article_id: int):
            assert article_id == ARTICLE_ID
            return _entry(has_embedding=False)

        def save_embedding(self, article_id: int, embedding: list[float]) -> None:
            from src.features.product.infrastructure.output.http.errors import (
                ProductEmbeddingEntryNotFoundError,
            )

            raise ProductEmbeddingEntryNotFoundError("Product not found.")

    class StubEmbeddingClient:
        def __init__(self, **kwargs) -> None:
            pass

        def embed(self, text: str) -> list[float]:
            return [0.1, 0.2]

    monkeypatch.setattr(main, "DatabaseProductEmbeddingStore", StubEmbeddingStore)
    _patch_embedding_client(monkeypatch, StubEmbeddingClient)

    client = _build_test_client(monkeypatch)
    response = client.post(EMBEDDING_ROUTE, headers=_build_auth_headers())

    assert response.status_code == 404
    assert response.json() == {"detail": "Product not found."}
