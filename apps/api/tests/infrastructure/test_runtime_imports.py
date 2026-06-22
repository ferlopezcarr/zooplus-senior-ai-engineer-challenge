from __future__ import annotations

from src.domain import Product
from src.infrastructure.input.http.chat.model import (
    ChatRequest,
    ChatResponse,
    ProductDTO,
)
from src.infrastructure.output.product_retriever import ProductRetriever
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


def test_product_retriever_is_importable_from_app_runtime() -> None:
    assert ProductRetriever.__module__ == "src.infrastructure.output.product_retriever"


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
