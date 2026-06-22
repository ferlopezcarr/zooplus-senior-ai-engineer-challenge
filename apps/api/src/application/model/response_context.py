from __future__ import annotations

from dataclasses import dataclass

from src.domain.model import Product


@dataclass(frozen=True)
class ResponseContext:
    products: list[Product]
