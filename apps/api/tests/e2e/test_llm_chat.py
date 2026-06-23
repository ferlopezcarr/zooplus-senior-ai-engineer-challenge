from __future__ import annotations

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

import main
from src.infrastructure.output.product_database_retriever import (
    DatabaseProductRetriever,
)


pytestmark = pytest.mark.e2e

_DETERMINISTIC_PREFIX = "For site "
TEST_DATABASE_URL = (
    "postgresql+asyncpg://test_user:test_password@example.test:5432/catalog"
)
CHAT_ROUTE = "/public/chat"
CATALOG_ROWS = [
    {
        "article_id": 1001,
        "product_id": "sensitive-salmon",
        "variant_id": "sensitive-salmon-1",
        "product_name": "Sensitive Salmon Food",
        "variant_name": "Adult Dog 12kg",
        "summary": "dog food for sensitive stomach",
        "description": "gentle dry food for adult dogs",
        "pet_type": "dog",
        "brands": "Calm Paws",
        "site_id": 1,
    },
    {
        "article_id": 1002,
        "product_id": "pienso-cordero",
        "variant_id": "pienso-cordero-1",
        "product_name": "Pienso Cordero",
        "variant_name": "Perro Adulto 10kg",
        "summary": "pienso para perro sensible",
        "description": "comida seca suave para digestion delicada",
        "pet_type": "dog",
        "brands": "Mascota Feliz",
        "site_id": 1,
    },
]


def _require_local_llm_config() -> None:
    load_dotenv(main.DOTENV_PATH)

    if main._get_non_blank_env("LLM_BASE_URL") and main._get_non_blank_env(
        "LLM_API_KEY"
    ):
        return

    pytest.skip(
        "Manual LLM e2e test requires non-blank LLM_BASE_URL and LLM_API_KEY "
        f"in the environment or {main.DOTENV_PATH}."
    )


def _build_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    _require_local_llm_config()
    monkeypatch.setattr(main, "_missing_llm_config_warnings_emitted", set())
    monkeypatch.setenv("PRODUCT_CATALOG_DATABASE_URL", TEST_DATABASE_URL)

    class StubDatabaseProductRetriever:
        def __init__(self, database_url: str) -> None:
            assert database_url == TEST_DATABASE_URL
            self._delegate = DatabaseProductRetriever(database_url)

            async def _load_rows_for_site(site_id: int, query_terms: set[str]):
                del query_terms
                return [row for row in CATALOG_ROWS if row["site_id"] == site_id]

            self._delegate._load_rows_for_site = _load_rows_for_site  # type: ignore[method-assign]

        def readiness_error(self) -> str | None:
            return None

        def retrieve(self, chat, limit: int = 3):
            return self._delegate.retrieve(chat, limit=limit)

    monkeypatch.setattr(main, "DatabaseProductRetriever", StubDatabaseProductRetriever)
    return TestClient(main.build_app())


def _assert_grounded_llm_answer(body: dict[str, object], *, spanish: bool) -> None:
    assert {"answer", "retrieved_products"}.issubset(body)

    answer = body["answer"]
    retrieved_products = body["retrieved_products"]

    assert isinstance(answer, str)
    assert answer.strip()
    assert not answer.startswith(_DETERMINISTIC_PREFIX)

    assert isinstance(retrieved_products, list)
    assert retrieved_products

    if spanish:
        expected_identifiers = {1002, "pienso-cordero"}
    else:
        expected_identifiers = {1001, "sensitive-salmon"}

    assert any(
        product.get("article_id") in expected_identifiers
        or product.get("product_id") in expected_identifiers
        for product in retrieved_products
        if isinstance(product, dict)
    )

    if spanish:
        assert any(
            token in answer.lower()
            for token in ("perro", "pienso", "comida", "sensible")
        )
    else:
        assert any(
            token in answer.lower() for token in ("dog", "sensitive", "salmon", "food")
        )


def test_chat_uses_real_llm_for_english_grounded_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _build_client(monkeypatch)

    response = client.post(
        CHAT_ROUTE,
        json={"site_id": 1, "query": "dog food for sensitive stomach"},
    )

    assert response.status_code == 200
    _assert_grounded_llm_answer(response.json(), spanish=False)


def test_chat_uses_real_llm_for_spanish_grounded_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _build_client(monkeypatch)

    response = client.post(
        CHAT_ROUTE,
        json={"site_id": 1, "query": "pienso para perro sensible"},
    )

    assert response.status_code == 200
    _assert_grounded_llm_answer(response.json(), spanish=True)
