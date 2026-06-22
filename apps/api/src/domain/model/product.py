from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Product:
    article_id: int
    product_id: str
    variant_id: str
    title: str
    summary: str
    site_id: int
    category: str
    score: float
