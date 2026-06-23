from __future__ import annotations

from dataclasses import dataclass

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

import main
from src.infrastructure.output.product_database_retriever import (
    DatabaseProductRetriever,
    PRODUCT_CATALOG_DATABASE_URL_ENV,
)


pytestmark = pytest.mark.e2e

CHAT_ROUTE = "/public/chat"
EMBEDDING_ROUTE_TEMPLATE = "/internal/products/{article_id}/embedding?force=true"
_DETERMINISTIC_PREFIX = "For site "


@dataclass(frozen=True)
class RuntimeConfig:
    database_url: str
    llm_enabled: bool
    embedding_enabled: bool
    internal_api_token: str | None


def _load_runtime_config() -> RuntimeConfig:
    load_dotenv(main.DOTENV_PATH)

    database_url = main._get_non_blank_env(PRODUCT_CATALOG_DATABASE_URL_ENV)
    if not database_url:
        pytest.skip(
            "Manual e2e runtime test requires non-blank PRODUCT_CATALOG_DATABASE_URL "
            f"in the environment or {main.DOTENV_PATH}."
        )

    try:
        readiness_error = DatabaseProductRetriever(database_url).readiness_error()
    except Exception:
        readiness_error = "database check failed"

    if readiness_error:
        pytest.skip(
            "Manual e2e runtime test requires a ready local catalog database. "
            "Run `uv run alembic upgrade head` and `uv run python scripts/product_catalog_feed.py` first."
        )

    llm_enabled = bool(main._get_non_blank_env("LLM_BASE_URL")) and bool(
        main._get_non_blank_env("LLM_API_KEY")
    )
    embedding_enabled = all(
        main._get_non_blank_env(name)
        for name in ("EMBEDDING_BASE_URL", "EMBEDDING_API_KEY", "EMBEDDING_MODEL")
    )

    return RuntimeConfig(
        database_url=database_url,
        llm_enabled=llm_enabled,
        embedding_enabled=embedding_enabled,
        internal_api_token=main._get_non_blank_env("INTERNAL_API_TOKEN"),
    )


@pytest.fixture
def runtime_config() -> RuntimeConfig:
    return _load_runtime_config()


@pytest.fixture
def client(
    runtime_config: RuntimeConfig, monkeypatch: pytest.MonkeyPatch
) -> TestClient:
    del runtime_config
    monkeypatch.setattr(main, "_missing_llm_config_warnings_emitted", set())
    return TestClient(main.build_app())


def _post_chat(client: TestClient, query: str) -> dict[str, object]:
    response = client.post(CHAT_ROUTE, json={"site_id": 1, "query": query})

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, dict)
    assert {"answer", "retrieved_products"}.issubset(body)

    answer = body["answer"]
    retrieved_products = body["retrieved_products"]

    assert isinstance(answer, str)
    assert answer.strip()
    assert isinstance(retrieved_products, list)
    assert retrieved_products

    for product in retrieved_products:
        assert isinstance(product, dict)
        assert isinstance(product.get("article_id"), int)
        assert isinstance(product.get("product_id"), str)
        assert isinstance(product.get("variant_id"), str)
        assert isinstance(product.get("title"), str)
        assert isinstance(product.get("summary"), str)
        assert product.get("site_id") == 1
        assert isinstance(product.get("category"), str)
        assert isinstance(product.get("score"), int | float)
        assert float(product["score"]) > 0

    return body


def test_health_endpoint_returns_process_status(
    runtime_config: RuntimeConfig, client: TestClient
) -> None:
    del runtime_config
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_public_chat_returns_catalog_matches_from_local_database(
    runtime_config: RuntimeConfig, client: TestClient
) -> None:
    del runtime_config
    body = _post_chat(client, query="dog ball fetch")

    assert any(token in body["answer"].lower() for token in ("dog", "ball", "fetch"))


def test_public_chat_uses_llm_when_local_llm_config_is_present(
    runtime_config: RuntimeConfig, client: TestClient
) -> None:
    if not runtime_config.llm_enabled:
        pytest.skip(
            "LLM e2e path skipped: set non-blank LLM_BASE_URL and LLM_API_KEY to verify provider-backed answers."
        )

    body = _post_chat(client, query="dog ball fetch")
    assert not body["answer"].startswith(_DETERMINISTIC_PREFIX)


def test_internal_embedding_route_recalculates_embedding_when_configured(
    runtime_config: RuntimeConfig, client: TestClient
) -> None:
    if not runtime_config.internal_api_token:
        pytest.skip(
            "Embedding e2e path skipped: set non-blank INTERNAL_API_TOKEN to verify internal maintenance routes."
        )

    if not runtime_config.embedding_enabled:
        pytest.skip(
            "Embedding e2e path skipped: set EMBEDDING_BASE_URL, EMBEDDING_API_KEY, and EMBEDDING_MODEL to verify provider-backed embeddings."
        )

    chat_body = _post_chat(client, query="dog ball fetch")
    article_id = chat_body["retrieved_products"][0]["article_id"]

    response = client.post(
        EMBEDDING_ROUTE_TEMPLATE.format(article_id=article_id),
        headers={"X-Internal-Token": runtime_config.internal_api_token},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["article_id"] == article_id
    assert body["status"] in {"embedded", "recalculated"}
    assert isinstance(body["model"], str)
    assert body["model"].strip()
    assert isinstance(body["dimensions"], int)
    assert body["dimensions"] > 0
