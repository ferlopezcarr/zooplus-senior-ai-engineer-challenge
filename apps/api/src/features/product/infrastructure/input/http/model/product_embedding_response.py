from pydantic import BaseModel

from src.features.product.infrastructure.input.http.model.product_embedding_status import (
    ProductEmbeddingStatus,
)


class ProductEmbeddingResponse(BaseModel):
    article_id: int
    status: ProductEmbeddingStatus
    model: str | None
    dimensions: int | None
