from __future__ import annotations

import importlib
import sys

from src.application.model.response_context import ResponseContext
from src.application.use_case.chat_use_case import ChatUseCase
from src.domain.model import Product
from src.infrastructure.input.http.chat.model import (
    ChatRequest,
    ChatResponse,
    ProductDTO,
)
from src.infrastructure.output.product_database_retriever import (
    DatabaseProductRetriever,
)
from src.infrastructure.output.service import to_product


def test_chat_model_package_exports_expected_symbols() -> None:
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

    request = ChatRequest(site_id=1, query="dog toy")

    assert request.site_id == 1
    assert isinstance(response.retrieved_products[0], ProductDTO)


def test_database_product_retriever_is_importable_from_app_runtime() -> None:
    assert (
        DatabaseProductRetriever.__module__
        == "src.infrastructure.output.product_database_retriever"
    )


def test_application_symbols_resolve_from_canonical_packages() -> None:
    assert ChatUseCase.__module__ == "src.application.use_case.chat_use_case"
    assert ResponseContext.__module__ == "src.application.model.response_context"


def test_output_product_mapper_keeps_runtime_product_shape() -> None:
    product = to_product(
        {
            "article_id": 1001,
            "product_id": "sku-1",
            "variant_id": "sku-1-red",
            "product_name": "Toy",
            "variant_name": "Large",
            "summary": "ball for fetch",
            "pet_type": "dog",
        },
        site_id=1,
        score=2.0,
    )

    assert product == Product(
        article_id=1001,
        product_id="sku-1",
        variant_id="sku-1-red",
        title="Toy - Large",
        summary="ball for fetch",
        site_id=1,
        category="dog",
        score=2.0,
    )


def test_main_module_import_does_not_build_app(monkeypatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "secret")
    monkeypatch.setenv("LLM_BASE_URL", "http://unsafe.test/v1")
    sys.modules.pop("main", None)

    module = importlib.import_module("main")

    assert not hasattr(module, "app")
    assert callable(module.build_app)
