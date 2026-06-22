from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main
from src.infrastructure.input.http.chat.model import ChatResponse, ProductDTO


def _write_dataset(tmp_path: Path, rows: list[dict[str, object]]) -> Path:
    dataset_path = tmp_path / "catalog.json"
    dataset_path.write_text(json.dumps(rows))
    return dataset_path


@pytest.fixture(autouse=True)
def _clear_llm_env(monkeypatch) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_TIMEOUT_SECONDS", raising=False)
    monkeypatch.setattr(main, "DOTENV_PATH", Path(".missing-test.env"))
    monkeypatch.setattr(main, "_missing_llm_config_warnings_emitted", set())


def test_chat_endpoint_uses_catalog_dataset_path_override(
    tmp_path: Path, monkeypatch
) -> None:
    dataset_path = _write_dataset(
        tmp_path,
        [
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
        ],
    )
    monkeypatch.setenv("CATALOG_DATASET_PATH", str(dataset_path))

    client = TestClient(main.build_app())
    response = client.post("/chat", json={"site_id": 77, "query": "env ball"})

    assert response.status_code == 200
    body = response.json()

    assert isinstance(body["answer"], str)
    assert body["answer"]
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


def test_chat_endpoint_allows_brand_only_catalog_queries(
    tmp_path: Path, monkeypatch
) -> None:
    dataset_path = _write_dataset(
        tmp_path,
        [
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
    monkeypatch.setenv("CATALOG_DATASET_PATH", str(dataset_path))

    client = TestClient(main.build_app())
    response = client.post("/chat", json={"site_id": 5, "query": "eukanuba"})

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


def test_chat_endpoint_uses_llm_answer_when_configured(
    tmp_path: Path, monkeypatch
) -> None:
    dataset_path = _write_dataset(
        tmp_path,
        [
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
        ],
    )

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

        def from_catalog(self, site_id: int, context) -> str:
            assert site_id == 77
            assert len(context.products) == 1
            return "Grounded answer from LLM"

    monkeypatch.setenv("CATALOG_DATASET_PATH", str(dataset_path))
    monkeypatch.setenv("LLM_API_KEY", "secret")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "2")
    monkeypatch.setattr(main, "OpenAICompatibleAnswerClient", StubAnswerClient)

    client = TestClient(main.build_app())
    response = client.post("/chat", json={"site_id": 77, "query": "env ball"})

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


def test_chat_endpoint_falls_back_when_llm_call_fails(
    tmp_path: Path, monkeypatch
) -> None:
    dataset_path = _write_dataset(
        tmp_path,
        [
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
        ],
    )

    class FailingAnswerClient:
        def __init__(self, **kwargs) -> None:
            pass

        def from_catalog(self, site_id: int, context) -> str:
            assert site_id == 77
            assert len(context.products) == 1
            raise TimeoutError("boom")

    monkeypatch.setenv("CATALOG_DATASET_PATH", str(dataset_path))
    monkeypatch.setenv("LLM_API_KEY", "secret")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setattr(main, "OpenAICompatibleAnswerClient", FailingAnswerClient)

    client = TestClient(main.build_app())
    response = client.post("/chat", json={"site_id": 77, "query": "env ball"})

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


def test_chat_endpoint_returns_dataset_backed_products_in_score_order(
    tmp_path: Path, monkeypatch
) -> None:
    dataset_path = _write_dataset(
        tmp_path,
        [
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
    monkeypatch.setenv("CATALOG_DATASET_PATH", str(dataset_path))

    client = TestClient(main.build_app())
    response = client.post("/chat", json={"site_id": 1, "query": "dog ball fetch"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()

    assert isinstance(body["answer"], str)
    assert body["answer"] == (
        "For site 1, I found these catalog matches: "
        "Omega Ball - Dog Fetch (dog): ball for dog fetch; "
        "Alpha Ball - Dog Toy (dog): ball for dog play; "
        "Beta Ball - Dog Toy (dog): ball for dog play."
    )
    assert body["retrieved_products"] == [
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
    ]


def test_chat_endpoint_ignores_dataset_rows_with_boolean_site_ids(
    tmp_path: Path, monkeypatch
) -> None:
    dataset_path = _write_dataset(
        tmp_path,
        [
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
    monkeypatch.setenv("CATALOG_DATASET_PATH", str(dataset_path))

    client = TestClient(main.build_app())
    response = client.post("/chat", json={"site_id": 1, "query": "dog ball fetch"})

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

    missing_site_response = client.post("/chat", json={"query": "dog food"})
    boolean_site_response = client.post(
        "/chat", json={"site_id": True, "query": "dog food"}
    )
    float_site_response = client.post(
        "/chat", json={"site_id": 1.0, "query": "dog food"}
    )
    string_site_response = client.post(
        "/chat", json={"site_id": "1", "query": "dog food"}
    )
    zero_padded_string_site_response = client.post(
        "/chat", json={"site_id": "01", "query": "dog food"}
    )
    zero_site_response = client.post("/chat", json={"site_id": 0, "query": "dog food"})
    negative_site_response = client.post(
        "/chat", json={"site_id": -1, "query": "dog food"}
    )
    empty_query_response = client.post("/chat", json={"site_id": 1, "query": "   "})
    semantic_query_response = client.post(
        "/chat", json={"site_id": 1, "query": "!!! &amp; ???"}
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


def test_chat_endpoint_rejects_malformed_json_requests() -> None:
    client = TestClient(main.build_app())

    response = client.post(
        "/chat",
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


def test_chat_endpoint_returns_503_when_dataset_file_is_missing(
    tmp_path: Path, monkeypatch
) -> None:
    missing_dataset_path = tmp_path / "missing.json"
    monkeypatch.setenv("CATALOG_DATASET_PATH", str(missing_dataset_path))

    client = TestClient(main.build_app())
    response = client.post("/chat", json={"site_id": 1, "query": "dog food"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Catalog dataset is unavailable."}
    assert str(missing_dataset_path) not in response.json()["detail"]


def test_chat_endpoint_returns_503_when_dataset_json_is_invalid(
    tmp_path: Path, monkeypatch
) -> None:
    dataset_path = tmp_path / "invalid.json"
    dataset_path.write_text("{not-valid-json")
    monkeypatch.setenv("CATALOG_DATASET_PATH", str(dataset_path))

    client = TestClient(main.build_app())
    response = client.post("/chat", json={"site_id": 1, "query": "dog food"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Catalog dataset is unavailable."}
    assert str(dataset_path) not in response.json()["detail"]


def test_chat_endpoint_returns_503_when_dataset_rows_are_malformed(
    tmp_path: Path, monkeypatch
) -> None:
    dataset_path = _write_dataset(
        tmp_path,
        [
            {
                "product_id": "broken-product",
                "product_name": "Broken Food",
                "summary": "dog food",
                "description": "missing variant name",
                "pet_type": "dog",
                "brands": "Broken",
                "site_id": 1,
            }
        ],
    )
    monkeypatch.setenv("CATALOG_DATASET_PATH", str(dataset_path))

    client = TestClient(main.build_app())
    response = client.post("/chat", json={"site_id": 1, "query": "dog food"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Catalog dataset is unavailable."}


def test_chat_endpoint_returns_503_when_article_id_is_not_an_integer(
    tmp_path: Path, monkeypatch
) -> None:
    dataset_path = _write_dataset(
        tmp_path,
        [
            {
                "article_id": "not-int",
                "product_id": "broken-product",
                "variant_id": "broken-product-1",
                "product_name": "Broken Food",
                "variant_name": "1kg",
                "summary": "dog food",
                "description": "bad article id",
                "pet_type": "dog",
                "brands": "Broken",
                "site_id": 1,
            }
        ],
    )
    monkeypatch.setenv("CATALOG_DATASET_PATH", str(dataset_path))

    client = TestClient(main.build_app())
    response = client.post("/chat", json={"site_id": 1, "query": "dog food"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Catalog dataset is unavailable."}


def test_chat_endpoint_normalizes_html_summary_in_answer_and_retrieved_products(
    tmp_path: Path, monkeypatch
) -> None:
    dataset_path = _write_dataset(
        tmp_path,
        [
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
    monkeypatch.setenv("CATALOG_DATASET_PATH", str(dataset_path))

    client = TestClient(main.build_app())
    response = client.post("/chat", json={"site_id": 1, "query": "omega dogs"})

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


def test_chat_endpoint_returns_503_when_dataset_root_json_is_not_an_array(
    tmp_path: Path,
    monkeypatch,
) -> None:
    dataset_path = tmp_path / "catalog.json"
    dataset_path.write_text(json.dumps({"product_id": "not-an-array"}))
    monkeypatch.setenv("CATALOG_DATASET_PATH", str(dataset_path))

    client = TestClient(main.build_app())
    response = client.post("/chat", json={"site_id": 1, "query": "dog food"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Catalog dataset is unavailable."}


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
