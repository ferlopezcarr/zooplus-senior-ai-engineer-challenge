from __future__ import annotations

from src.infrastructure.input.http.chat.model.product_dto import ProductDTO
from pydantic import BaseModel


class ChatResponse(BaseModel):
    answer: str
    retrieved_products: list[ProductDTO]
