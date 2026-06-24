from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main
from src.features.chat.domain.model.product import Product
from src.features.chat.infrastructure.input.http.model.chat_response import ChatResponse
from src.features.chat.infrastructure.input.http.model.product_dto import ProductDTO
from src.features.chat.infrastructure.output.http.errors import (
    CatalogDatabaseUnavailableError,
)
from src.features.chat.infrastructure.output.persistence.product_database_retriever import (
    ProductDatabaseRetriever,
)


TEST_DATABASE_URL = (
    "postgresql+psycopg://test_user:test_password@example.test:5432/catalog"
)
CHAT_ROUTE = "/public/chat"
ENV_ONLY_ROWS = [
    {
        "article_id": 2001,
        "product_id": "env-only-product",
        "variant_id": "env-only-product-1",
        "product_name": "Env Only Ball",
        "variant_name": "Dog Toy",
        "summary": "ball for dog fetch",
        "description": "small override dataset row",
        "pet_type": "dog",
        "brands": "Env Brand",
        "site_id": 77,
    }
]


def _patch_database_retriever(
    monkeypatch,
    *,
    rows: list[dict[str, object]] | None = None,
    vector_rows: list[dict[str, object]] | None = None,
    retrieval_error: Exception | None = None,
) -> None:
    class StubProductDatabaseRetriever:
        def __init__(
            self,
            database_url: str,
            embedding_client_factory=None,
        ) -> None:
            assert database_url == TEST_DATABASE_URL
            self._delegate = ProductDatabaseRetriever(
                database_url,
                embedding_client_factory=embedding_client_factory,
            )
            self._embedding_client_factory = embedding_client_factory

            def _load_rows_for_site(
                site_id: int,
                query_terms: set[str],
            ) -> list[dict[str, object]]:
                del query_terms
                return [
                    row
                    for row in (rows or [])
                    if isinstance(row["site_id"], int)
                    and not isinstance(row["site_id"], bool)
                    and row["site_id"] == site_id
                ]

            self._delegate._catalog_reader.load_rows_for_site = _load_rows_for_site  # type: ignore[method-assign]

            def _load_vector_rows_for_site(
                site_id: int,
                embedding: list[float],
                *,
                limit: int,
            ) -> list[dict[str, object]]:
                del embedding
                return [
                    row
                    for row in (vector_rows or [])[:limit]
                    if isinstance(row["site_id"], int)
                    and not isinstance(row["site_id"], bool)
                    and row["site_id"] == site_id
                ]

            self._delegate._catalog_reader.load_vector_rows_for_site = (
                _load_vector_rows_for_site  # type: ignore[method-assign]
            )

        def readiness_error(self) -> str | None:
            return None

        def retrieve(self, chat, limit: int = 3) -> list[Product]:
            if retrieval_error is not None:
                raise retrieval_error
            return self._delegate.retrieve(chat, limit=limit)

    monkeypatch.setattr(main, "ProductDatabaseRetriever", StubProductDatabaseRetriever)


@pytest.fixture(autouse=True)
def _clear_llm_env(monkeypatch) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("EMBEDDING_BASE_URL", raising=False)
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("EMBEDDING_TIMEOUT_SECONDS", raising=False)
    monkeypatch.setenv("PRODUCT_CATALOG_DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setattr(main, "DOTENV_PATH", Path(".missing-test.env"))
    monkeypatch.setattr(main, "_missing_llm_config_warnings_emitted", set())
    monkeypatch.setattr(main, "_embedding_retrieval_warnings_emitted", set())
    _patch_database_retriever(monkeypatch, rows=ENV_ONLY_ROWS)


def test_chat_endpoint_returns_postgresql_backed_products() -> None:
    client = TestClient(main.build_app())
    response = client.post(CHAT_ROUTE, json={"site_id": 77, "query": "env ball"})

    assert response.status_code == 200
    assert response.json()["retrieved_products"] == [
        {
            "article_id": 2001,
            "product_id": "env-only-product",
            "variant_id": "env-only-product-1",
            "title": "Env Only Ball - Dog Toy",
            "summary": "ball for dog fetch",
            "site_id": 77,
            "category": "dog",
            "score": 2.0,
        }
    ]


def test_chat_endpoint_hides_products_for_off_topic_queries(monkeypatch) -> None:
    class StubProductDatabaseRetriever:
        def __init__(
            self,
            database_url: str,
            embedding_client_factory=None,
        ) -> None:
            assert database_url == TEST_DATABASE_URL
            del embedding_client_factory

        def readiness_error(self) -> str | None:
            return None

        def retrieve(self, chat, limit: int = 3) -> list[Product]:
            assert chat.query.value == "what is the weather today"
            assert limit == 3
            return [
                Product(
                    article_id=2001,
                    product_id="env-only-product",
                    variant_id="env-only-product-1",
                    title="Env Only Ball - Dog Toy",
                    summary="ball for dog fetch",
                    site_id=77,
                    category="dog",
                    score=2.0,
                )
            ]

    monkeypatch.setattr(main, "ProductDatabaseRetriever", StubProductDatabaseRetriever)

    client = TestClient(main.build_app())
    response = client.post(
        CHAT_ROUTE,
        json={"site_id": 77, "query": "what is the weather today"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "I can only help with pet products that exist in the provided catalog.",
        "retrieved_products": [],
    }


def test_chat_endpoint_hides_products_for_single_word_off_topic_queries(
    monkeypatch,
) -> None:
    class StubProductDatabaseRetriever:
        def __init__(
            self,
            database_url: str,
            embedding_client_factory=None,
        ) -> None:
            assert database_url == TEST_DATABASE_URL
            del embedding_client_factory

        def readiness_error(self) -> str | None:
            return None

        def retrieve(self, chat, limit: int = 3) -> list[Product]:
            assert chat.query.value == "bitcoin"
            assert limit == 3
            return [
                Product(
                    article_id=2001,
                    product_id="env-only-product",
                    variant_id="env-only-product-1",
                    title="Env Only Ball - Dog Toy",
                    summary="ball for dog fetch",
                    site_id=77,
                    category="dog",
                    score=2.0,
                )
            ]

    monkeypatch.setattr(main, "ProductDatabaseRetriever", StubProductDatabaseRetriever)

    client = TestClient(main.build_app())
    response = client.post(CHAT_ROUTE, json={"site_id": 77, "query": "bitcoin"})

    assert response.status_code == 200
    assert response.json() == {
        "answer": "I can only help with pet products that exist in the provided catalog.",
        "retrieved_products": [],
    }


def test_chat_endpoint_allows_brand_only_catalog_queries(monkeypatch) -> None:
    _patch_database_retriever(
        monkeypatch,
        rows=[
            {
                "article_id": 3001,
                "product_id": "brand-only-product",
                "variant_id": "brand-only-product-1",
                "product_name": "Sensitive Dry Food",
                "variant_name": "12kg",
                "summary": "complete nutrition",
                "description": "adult dog food",
                "pet_type": "dog",
                "brands": "Eukanuba",
                "site_id": 5,
            }
        ],
    )
    client = TestClient(main.build_app())
    response = client.post(CHAT_ROUTE, json={"site_id": 5, "query": "eukanuba"})

    assert response.status_code == 200
    assert response.json()["retrieved_products"] == [
        {
            "article_id": 3001,
            "product_id": "brand-only-product",
            "variant_id": "brand-only-product-1",
            "title": "Sensitive Dry Food - 12kg",
            "summary": "complete nutrition",
            "site_id": 5,
            "category": "dog",
            "score": 1.0,
        }
    ]


def test_chat_endpoint_allows_multi_word_brand_catalog_queries(monkeypatch) -> None:
    _patch_database_retriever(
        monkeypatch,
        rows=[
            {
                "article_id": 3002,
                "product_id": "royal-canin-product",
                "variant_id": "royal-canin-product-1",
                "product_name": "Digestive Care",
                "variant_name": "12kg",
                "summary": "complete nutrition",
                "description": "adult dog food",
                "pet_type": "dog",
                "brands": "Royal Canin",
                "site_id": 5,
            }
        ],
    )
    client = TestClient(main.build_app())
    response = client.post(CHAT_ROUTE, json={"site_id": 5, "query": "royal canin"})

    assert response.status_code == 200
    assert response.json()["retrieved_products"] == [
        {
            "article_id": 3002,
            "product_id": "royal-canin-product",
            "variant_id": "royal-canin-product-1",
            "title": "Digestive Care - 12kg",
            "summary": "complete nutrition",
            "site_id": 5,
            "category": "dog",
            "score": 2.0,
        }
    ]


def test_chat_endpoint_uses_database_retriever_when_database_url_is_configured(
    monkeypatch,
) -> None:
    class StubProductDatabaseRetriever:
        def __init__(
            self,
            database_url: str,
            embedding_client_factory=None,
        ) -> None:
            assert database_url == TEST_DATABASE_URL
            assert embedding_client_factory is None

        def readiness_error(self) -> str | None:
            return None

        def retrieve(self, chat, limit: int = 3) -> list[Product]:
            assert chat.site_id.value == 77
            assert chat.query.value == "env ball"
            assert limit == 3
            return [
                Product(
                    article_id=2001,
                    product_id="env-only-product",
                    variant_id="env-only-product-1",
                    title="Env Only Ball - Dog Toy",
                    summary="ball for dog fetch",
                    site_id=77,
                    category="dog",
                    score=2.0,
                )
            ]

    monkeypatch.setattr(main, "ProductDatabaseRetriever", StubProductDatabaseRetriever)

    client = TestClient(main.build_app())
    response = client.post(CHAT_ROUTE, json={"site_id": 77, "query": "env ball"})

    assert response.status_code == 200
    assert response.json()["retrieved_products"] == [
        {
            "article_id": 2001,
            "product_id": "env-only-product",
            "variant_id": "env-only-product-1",
            "title": "Env Only Ball - Dog Toy",
            "summary": "ball for dog fetch",
            "site_id": 77,
            "category": "dog",
            "score": 2.0,
        }
    ]


def test_chat_endpoint_enables_vector_retrieval_when_embedding_config_is_complete(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    class StubProductDatabaseRetriever:
        def __init__(
            self,
            database_url: str,
            embedding_client_factory=None,
        ) -> None:
            assert database_url == TEST_DATABASE_URL
            captured["factory"] = embedding_client_factory

        def readiness_error(self) -> str | None:
            return None

        def retrieve(self, chat, limit: int = 3) -> list[Product]:
            return []

    class StubEmbeddingClient:
        model = "test-embedding-model"

        def __init__(self, **kwargs) -> None:
            captured["embedding_kwargs"] = kwargs

        def embed(self, text: str) -> list[float]:
            return [0.1, 0.2]

    monkeypatch.setenv(
        "EMBEDDING_BASE_URL", "https://embeddings.example.test/v1/embeddings"
    )
    monkeypatch.setenv("EMBEDDING_API_KEY", "secret")
    monkeypatch.setenv("EMBEDDING_MODEL", "test-embedding-model")
    monkeypatch.setattr(main, "ProductDatabaseRetriever", StubProductDatabaseRetriever)
    monkeypatch.setattr(main, "OpenAICompatibleEmbeddingClient", StubEmbeddingClient)

    main.build_app()

    factory = captured["factory"]
    assert callable(factory)
    client = factory()
    assert isinstance(client, StubEmbeddingClient)
    assert captured["embedding_kwargs"] == {
        "api_key": "secret",
        "model": "test-embedding-model",
        "base_url": "https://embeddings.example.test/v1/embeddings",
        "timeout_seconds": 10.0,
    }


def test_chat_endpoint_uses_lexical_top_up_after_dropping_below_threshold_vector_hits(
    monkeypatch,
) -> None:
    class StubEmbeddingClient:
        def __init__(self, **kwargs) -> None:
            del kwargs

        def embed(self, text: str) -> list[float]:
            assert text == "dog ball"
            return [0.1, 0.2]

    _patch_database_retriever(
        monkeypatch,
        rows=[
            {
                "article_id": 9001,
                "product_id": "lexical-alpha",
                "variant_id": "lexical-alpha-1",
                "product_name": "Alpha Ball",
                "variant_name": "Fetch Toy",
                "summary": "dog ball for fetch",
                "description": "exact lexical match",
                "pet_type": "dog",
                "brands": "Alpha",
                "site_id": 1,
            },
            {
                "article_id": 9002,
                "product_id": "lexical-beta",
                "variant_id": "lexical-beta-1",
                "product_name": "Beta Ball",
                "variant_name": "Dog Toy",
                "summary": "dog ball for play",
                "description": "second lexical match",
                "pet_type": "dog",
                "brands": "Beta",
                "site_id": 1,
            },
        ],
        vector_rows=[
            {
                "article_id": 8001,
                "product_id": "vector-kept",
                "variant_id": "vector-kept-1",
                "product_name": "Vector Match",
                "variant_name": "Toy",
                "summary": "semantic dog ball match",
                "description": "kept at threshold",
                "pet_type": "dog",
                "brands": "Vector",
                "site_id": 1,
                "distance": 0.7,
            },
            {
                "article_id": 8002,
                "product_id": "vector-dropped",
                "variant_id": "vector-dropped-1",
                "product_name": "Vector Noise",
                "variant_name": "Toy",
                "summary": "irrelevant semantic miss",
                "description": "below threshold",
                "pet_type": "dog",
                "brands": "Vector",
                "site_id": 1,
                "distance": 0.71,
            },
        ],
    )
    monkeypatch.setenv(
        "EMBEDDING_BASE_URL", "https://embeddings.example.test/v1/embeddings"
    )
    monkeypatch.setenv("EMBEDDING_API_KEY", "secret")
    monkeypatch.setenv("EMBEDDING_MODEL", "test-embedding-model")
    monkeypatch.setattr(main, "OpenAICompatibleEmbeddingClient", StubEmbeddingClient)

    client = TestClient(main.build_app())
    response = client.post(CHAT_ROUTE, json={"site_id": 1, "query": "dog ball"})

    assert response.status_code == 200
    payload = response.json()
    retrieved_products = payload["retrieved_products"]

    assert payload == {
        "answer": (
            "For site 1, I found these catalog matches: "
            "Vector Match - Toy (dog): semantic dog ball match; "
            "Alpha Ball - Fetch Toy (dog): dog ball for fetch; "
            "Beta Ball - Dog Toy (dog): dog ball for play."
        ),
        "retrieved_products": [
            retrieved_products[0],
            {
                "article_id": 9001,
                "product_id": "lexical-alpha",
                "variant_id": "lexical-alpha-1",
                "title": "Alpha Ball - Fetch Toy",
                "summary": "dog ball for fetch",
                "site_id": 1,
                "category": "dog",
                "score": 2.0,
            },
            {
                "article_id": 9002,
                "product_id": "lexical-beta",
                "variant_id": "lexical-beta-1",
                "title": "Beta Ball - Dog Toy",
                "summary": "dog ball for play",
                "site_id": 1,
                "category": "dog",
                "score": 2.0,
            },
        ],
    }
    assert {
        key: value for key, value in retrieved_products[0].items() if key != "score"
    } == {
        "article_id": 8001,
        "product_id": "vector-kept",
        "variant_id": "vector-kept-1",
        "title": "Vector Match - Toy",
        "summary": "semantic dog ball match",
        "site_id": 1,
        "category": "dog",
    }
    assert retrieved_products[0]["score"] >= 0.3


def test_chat_endpoint_disables_vector_retrieval_when_embedding_config_is_invalid(
    monkeypatch,
    caplog,
) -> None:
    captured: dict[str, object] = {}

    class StubProductDatabaseRetriever:
        def __init__(
            self,
            database_url: str,
            embedding_client_factory=None,
        ) -> None:
            assert database_url == TEST_DATABASE_URL
            captured["factory"] = embedding_client_factory

        def readiness_error(self) -> str | None:
            return None

        def retrieve(self, chat, limit: int = 3) -> list[Product]:
            return []

    monkeypatch.setenv(
        "EMBEDDING_BASE_URL", "https://embeddings.example.test/v1/embeddings?extra=1"
    )
    monkeypatch.setenv("EMBEDDING_API_KEY", "secret")
    monkeypatch.setenv("EMBEDDING_MODEL", "test-embedding-model")
    monkeypatch.setattr(main, "ProductDatabaseRetriever", StubProductDatabaseRetriever)
    caplog.set_level("WARNING")

    main.build_app()

    assert captured["factory"] is None
    assert (
        "Invalid embedding provider config; /public/chat will use lexical fallback."
        in [record.getMessage() for record in caplog.records]
    )


@pytest.mark.parametrize("database_url", ["", "   "])
def test_chat_endpoint_fails_fast_when_database_url_is_blank(
    database_url: str, monkeypatch
) -> None:
    monkeypatch.setenv("PRODUCT_CATALOG_DATABASE_URL", database_url)

    with pytest.raises(ValueError, match="PRODUCT_CATALOG_DATABASE_URL"):
        main.build_app()


def test_chat_endpoint_uses_generic_retrieval_wording_when_database_fails(
    monkeypatch,
) -> None:
    _patch_database_retriever(
        monkeypatch,
        retrieval_error=CatalogDatabaseUnavailableError(
            "Catalog retrieval is unavailable."
        ),
    )

    client = TestClient(main.build_app())
    response = client.post(CHAT_ROUTE, json={"site_id": 77, "query": "env ball"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Catalog retrieval is unavailable."}


def test_chat_endpoint_uses_llm_answer_when_configured(monkeypatch) -> None:
    class StubAnswerClient:
        def __init__(
            self,
            api_key: str,
            model: str,
            base_url: str,
            timeout_seconds: float,
        ) -> None:
            assert api_key == "secret"
            assert model == "test-model"
            assert base_url == "https://example.test/v1"
            assert timeout_seconds == 2.0

        def from_catalog(self, site_id: int, query: str, context) -> str:
            assert site_id == 77
            assert query == "env ball"
            assert len(context.products) == 1
            return "Grounded answer from LLM"

    monkeypatch.setenv("LLM_API_KEY", "secret")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "2")
    monkeypatch.setattr(main, "OpenAICompatibleAnswerClient", StubAnswerClient)

    client = TestClient(main.build_app())
    response = client.post(CHAT_ROUTE, json={"site_id": 77, "query": "env ball"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Grounded answer from LLM"
    assert body["retrieved_products"] == [
        {
            "article_id": 2001,
            "product_id": "env-only-product",
            "variant_id": "env-only-product-1",
            "title": "Env Only Ball - Dog Toy",
            "summary": "ball for dog fetch",
            "site_id": 77,
            "category": "dog",
            "score": 2.0,
        }
    ]


def test_chat_endpoint_falls_back_when_llm_call_fails(monkeypatch) -> None:
    class FailingAnswerClient:
        def __init__(self, **kwargs) -> None:
            pass

        def from_catalog(self, site_id: int, query: str, context) -> str:
            assert site_id == 77
            assert query == "env ball"
            assert len(context.products) == 1
            raise TimeoutError("boom")

    monkeypatch.setenv("LLM_API_KEY", "secret")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setattr(main, "OpenAICompatibleAnswerClient", FailingAnswerClient)

    client = TestClient(main.build_app())
    response = client.post(CHAT_ROUTE, json={"site_id": 77, "query": "env ball"})

    assert response.status_code == 200
    assert response.json() == {
        "answer": (
            "For site 77, I found these catalog matches: "
            "Env Only Ball - Dog Toy (dog): ball for dog fetch."
        ),
        "retrieved_products": [
            {
                "article_id": 2001,
                "product_id": "env-only-product",
                "variant_id": "env-only-product-1",
                "title": "Env Only Ball - Dog Toy",
                "summary": "ball for dog fetch",
                "site_id": 77,
                "category": "dog",
                "score": 2.0,
            }
        ],
    }


def test_chat_endpoint_returns_products_in_score_order(monkeypatch) -> None:
    _patch_database_retriever(
        monkeypatch,
        rows=[
            {
                "article_id": 4002,
                "product_id": "beta-ball",
                "variant_id": "beta-ball-1",
                "product_name": "Beta Ball",
                "variant_name": "Dog Toy",
                "summary": "ball for dog play",
                "description": "durable dog toy",
                "pet_type": "dog",
                "brands": "Beta",
                "site_id": 1,
            },
            {
                "article_id": 4001,
                "product_id": "alpha-ball",
                "variant_id": "alpha-ball-1",
                "product_name": "Alpha Ball",
                "variant_name": "Dog Toy",
                "summary": "ball for dog play",
                "description": "light dog toy",
                "pet_type": "dog",
                "brands": "Alpha",
                "site_id": 1,
            },
            {
                "article_id": 4000,
                "product_id": "omega-ball",
                "variant_id": "omega-ball-1",
                "product_name": "Omega Ball",
                "variant_name": "Dog Fetch",
                "summary": "ball for dog fetch",
                "description": "fetch toy",
                "pet_type": "dog",
                "brands": "Omega",
                "site_id": 1,
            },
            {
                "article_id": 4999,
                "product_id": "offsite-ball",
                "variant_id": "offsite-ball-1",
                "product_name": "Offsite Ball",
                "variant_name": "Dog Fetch",
                "summary": "ball for dog fetch",
                "description": "wrong site row",
                "pet_type": "dog",
                "brands": "Elsewhere",
                "site_id": 2,
            },
        ],
    )

    client = TestClient(main.build_app())
    response = client.post(CHAT_ROUTE, json={"site_id": 1, "query": "dog ball fetch"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {
        "answer": (
            "For site 1, I found these catalog matches: "
            "Omega Ball - Dog Fetch (dog): ball for dog fetch; "
            "Alpha Ball - Dog Toy (dog): ball for dog play; "
            "Beta Ball - Dog Toy (dog): ball for dog play."
        ),
        "retrieved_products": [
            {
                "article_id": 4000,
                "product_id": "omega-ball",
                "variant_id": "omega-ball-1",
                "title": "Omega Ball - Dog Fetch",
                "summary": "ball for dog fetch",
                "site_id": 1,
                "category": "dog",
                "score": 3.0,
            },
            {
                "article_id": 4001,
                "product_id": "alpha-ball",
                "variant_id": "alpha-ball-1",
                "title": "Alpha Ball - Dog Toy",
                "summary": "ball for dog play",
                "site_id": 1,
                "category": "dog",
                "score": 2.0,
            },
            {
                "article_id": 4002,
                "product_id": "beta-ball",
                "variant_id": "beta-ball-1",
                "title": "Beta Ball - Dog Toy",
                "summary": "ball for dog play",
                "site_id": 1,
                "category": "dog",
                "score": 2.0,
            },
        ],
    }


def test_chat_endpoint_ignores_boolean_site_rows(monkeypatch) -> None:
    _patch_database_retriever(
        monkeypatch,
        rows=[
            {
                "article_id": 5000,
                "product_id": "boolean-site-row",
                "variant_id": "boolean-site-row-1",
                "product_name": "Boolean Site Ball",
                "variant_name": "Dog Fetch",
                "summary": "dog ball fetch",
                "description": "malformed site id row",
                "pet_type": "dog",
                "brands": "Broken",
                "site_id": True,
            },
            {
                "article_id": 5001,
                "product_id": "valid-site-row",
                "variant_id": "valid-site-row-1",
                "product_name": "Valid Site Ball",
                "variant_name": "Dog Fetch",
                "summary": "dog ball fetch",
                "description": "valid site id row",
                "pet_type": "dog",
                "brands": "Valid",
                "site_id": 1,
            },
        ],
    )

    client = TestClient(main.build_app())
    response = client.post(CHAT_ROUTE, json={"site_id": 1, "query": "dog ball fetch"})

    assert response.status_code == 200
    assert response.json()["retrieved_products"] == [
        {
            "article_id": 5001,
            "product_id": "valid-site-row",
            "variant_id": "valid-site-row-1",
            "title": "Valid Site Ball - Dog Fetch",
            "summary": "dog ball fetch",
            "site_id": 1,
            "category": "dog",
            "score": 3.0,
        }
    ]


def test_chat_endpoint_rejects_invalid_requests() -> None:
    client = TestClient(main.build_app())

    missing_site_response = client.post(CHAT_ROUTE, json={"query": "dog food"})
    boolean_site_response = client.post(
        CHAT_ROUTE, json={"site_id": True, "query": "dog food"}
    )
    float_site_response = client.post(
        CHAT_ROUTE, json={"site_id": 1.0, "query": "dog food"}
    )
    string_site_response = client.post(
        CHAT_ROUTE, json={"site_id": "1", "query": "dog food"}
    )
    zero_padded_string_site_response = client.post(
        CHAT_ROUTE, json={"site_id": "01", "query": "dog food"}
    )
    zero_site_response = client.post(
        CHAT_ROUTE, json={"site_id": 0, "query": "dog food"}
    )
    negative_site_response = client.post(
        CHAT_ROUTE, json={"site_id": -1, "query": "dog food"}
    )
    empty_query_response = client.post(CHAT_ROUTE, json={"site_id": 1, "query": "   "})
    semantic_query_response = client.post(
        CHAT_ROUTE, json={"site_id": 1, "query": "!!! &amp; ???"}
    )
    long_query_response = client.post(
        CHAT_ROUTE, json={"site_id": 1, "query": "a" * 501}
    )

    assert missing_site_response.status_code == 422
    assert boolean_site_response.status_code == 422
    assert float_site_response.status_code == 422
    assert string_site_response.status_code == 422
    assert zero_padded_string_site_response.status_code == 422
    assert zero_site_response.status_code == 422
    assert negative_site_response.status_code == 422
    assert empty_query_response.status_code == 422
    assert semantic_query_response.status_code == 422
    assert long_query_response.status_code == 422


def test_chat_endpoint_rejects_malformed_json_requests() -> None:
    client = TestClient(main.build_app())

    response = client.post(
        CHAT_ROUTE,
        content='{"site_id": 1,',
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()

    assert isinstance(body.get("detail"), list)
    assert body["detail"]
    assert body["detail"][0]["loc"][0] == "body"
    assert isinstance(body["detail"][0]["msg"], str)
    assert body["detail"][0]["msg"]
    assert isinstance(body["detail"][0]["type"], str)
    assert body["detail"][0]["type"]


def test_chat_endpoint_normalizes_html_summary_in_answer_and_retrieved_products(
    monkeypatch,
) -> None:
    _patch_database_retriever(
        monkeypatch,
        rows=[
            {
                "article_id": 6001,
                "product_id": "html-summary-product",
                "variant_id": "html-summary-product-1",
                "product_name": "Omega Ball",
                "variant_name": "Dog Fetch",
                "summary": "Ball for <b>dogs</b> &amp; cats",
                "description": "html summary row",
                "pet_type": "dog",
                "brands": "Omega",
                "site_id": 1,
            }
        ],
    )

    client = TestClient(main.build_app())
    response = client.post(CHAT_ROUTE, json={"site_id": 1, "query": "omega dogs"})

    assert response.status_code == 200
    assert response.json() == {
        "answer": (
            "For site 1, I found these catalog matches: "
            "Omega Ball - Dog Fetch (dog): Ball for dogs & cats."
        ),
        "retrieved_products": [
            {
                "article_id": 6001,
                "product_id": "html-summary-product",
                "variant_id": "html-summary-product-1",
                "title": "Omega Ball - Dog Fetch",
                "summary": "Ball for dogs & cats",
                "site_id": 1,
                "category": "dog",
                "score": 2.0,
            }
        ],
    }


def test_http_model_package_exports_product_dto() -> None:
    response = ChatResponse(
        answer="ok",
        retrieved_products=[
            ProductDTO(
                article_id=1001,
                product_id="sku-1",
                variant_id="sku-1-red",
                title="Toy",
                summary="ball for fetch",
                site_id=1,
                category="dog",
                score=1.0,
            )
        ],
    )

    assert isinstance(response.retrieved_products[0], ProductDTO)
