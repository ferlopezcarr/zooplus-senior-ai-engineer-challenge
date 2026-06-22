from __future__ import annotations

from pydantic import BaseModel


class ProductDTO(BaseModel):
    article_id: int
    product_id: str
    variant_id: str
    title: str
    summary: str
    site_id: int
    category: str
    score: float
