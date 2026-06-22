from __future__ import annotations

from dataclasses import dataclass

from src.domain.product import Product


@dataclass(frozen=True)
class ResponseContext:
    products: list[Product]
