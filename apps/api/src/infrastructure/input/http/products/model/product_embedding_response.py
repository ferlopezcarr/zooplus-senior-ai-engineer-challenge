from typing import Literal

from pydantic import BaseModel


ProductEmbeddingStatus = Literal[
    "already_embedded",
    "embedded",
    "recalculated",
]


class ProductEmbeddingResponse(BaseModel):
    article_id: int
    status: ProductEmbeddingStatus
    model: str | None
    dimensions: int | None
