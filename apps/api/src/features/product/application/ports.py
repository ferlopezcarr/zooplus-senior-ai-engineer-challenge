from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ProductEmbeddingEntry:
    article_id: int
    embedding_document: str
    has_embedding: bool


class ProductEmbeddingProviderPort(Protocol):
    model: str | None

    def embed(self, text: str) -> list[float]: ...


class ProductEmbeddingStorePort(Protocol):
    def get_entry(self, article_id: int) -> ProductEmbeddingEntry | None: ...

    def save_embedding(self, article_id: int, embedding: list[float]) -> None: ...
