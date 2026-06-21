from __future__ import annotations

from src.domain import Chat, ChatResult, Product, Query, SiteId
from src.infrastructure.input.http.chat.model import (
    ChatRequest,
    ChatResponse,
    ProductDTO,
)


def to_chat(body: ChatRequest) -> Chat:
    return Chat(site_id=SiteId(body.site_id), query=Query(body.query))


def to_chat_response(result: ChatResult) -> ChatResponse:
    return ChatResponse(
        answer=result.answer,
        retrieved_products=[
            to_product_dto(product) for product in result.retrieved_products
        ],
    )


def to_product_dto(product: Product) -> ProductDTO:
    return ProductDTO(**product.__dict__)
