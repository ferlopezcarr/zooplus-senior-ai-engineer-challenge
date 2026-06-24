from pydantic import BaseModel

from src.features.chat.infrastructure.input.http.model.product_dto import ProductDTO


class ChatResponse(BaseModel):
    answer: str
    retrieved_products: list[ProductDTO]
