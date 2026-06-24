from __future__ import annotations

from typing import Protocol

from src.features.chat.domain.model import Chat, Product


class ProductRetrievalPort(Protocol):
    def retrieve(self, chat: Chat) -> list[Product]: ...
