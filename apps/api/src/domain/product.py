from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Product:
    product_id: str
    title: str
    site_id: int
    category: str
    score: float
