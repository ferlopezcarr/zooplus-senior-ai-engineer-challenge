from __future__ import annotations

from src.domain import Chat, ChatResult, Product, Query, SiteId
from src.infrastructure.input.http.chat.service.chat_mapper import (
    to_chat,
    to_chat_response,
)
from src.infrastructure.input.http.chat.model import ChatRequest, ProductDTO


def test_to_chat_maps_http_request_into_chat() -> None:
    chat = to_chat(ChatRequest(site_id=7, query="Dog Ball"))

    assert chat == Chat(site_id=SiteId(7), query=Query("Dog Ball"))


def test_to_chat_response_maps_result_products_into_product_dtos() -> None:
    response = to_chat_response(
        ChatResult(
            answer="ok",
            retrieved_products=[
                Product(
                    product_id="sku-1",
                    title="Toy",
                    site_id=1,
                    category="dog",
                    score=2.0,
                ),
                Product(
                    product_id="sku-2",
                    title="Food",
                    site_id=1,
                    category="dog",
                    score=1.0,
                ),
            ],
        )
    )

    assert response.answer == "ok"
    assert response.retrieved_products == [
        ProductDTO(
            product_id="sku-1", title="Toy", site_id=1, category="dog", score=2.0
        ),
        ProductDTO(
            product_id="sku-2", title="Food", site_id=1, category="dog", score=1.0
        ),
    ]
