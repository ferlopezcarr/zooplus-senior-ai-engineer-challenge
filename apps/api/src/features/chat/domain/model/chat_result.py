from __future__ import annotations

from dataclasses import dataclass

from src.features.chat.domain.model.product import Product


@dataclass(frozen=True)
class ChatResult:
    answer: str
    retrieved_products: list[Product]
