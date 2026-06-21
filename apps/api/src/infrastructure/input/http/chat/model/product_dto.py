from __future__ import annotations

from pydantic import BaseModel


class ProductDTO(BaseModel):
    product_id: str
    title: str
    site_id: int
    category: str
    score: float
