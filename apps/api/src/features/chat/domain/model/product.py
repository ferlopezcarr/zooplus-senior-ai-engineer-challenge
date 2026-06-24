from __future__ import annotations

from dataclasses import dataclass, field


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
    search_text: str = field(default="", compare=False, repr=False)
