from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from src.features.product.application.ports import (
    ProductEmbeddingProviderPort,
    ProductEmbeddingStorePort,
)

ProductEmbeddingStatus = Literal[
    "already_embedded",
    "embedded",
    "recalculated",
]


@dataclass(frozen=True)
class ProductEmbeddingResult:
    article_id: int
    status: ProductEmbeddingStatus
    model: str | None
    dimensions: int | None


class ProductEmbeddingNotFoundError(Exception):
    pass


class ProductEmbeddingUseCase:
    def __init__(
        self,
        store: ProductEmbeddingStorePort,
        embedding_provider_factory: Callable[[], ProductEmbeddingProviderPort],
    ) -> None:
        self._store = store
        self._embedding_provider_factory = embedding_provider_factory

    def handle(self, article_id: int, *, force: bool) -> ProductEmbeddingResult:
        entry = self._store.get_entry(article_id)
        if entry is None:
            raise ProductEmbeddingNotFoundError("Product not found.")

        if entry.has_embedding and not force:
            return ProductEmbeddingResult(
                article_id=article_id,
                status="already_embedded",
                model=None,
                dimensions=None,
            )

        provider = self._embedding_provider_factory()
        embedding = provider.embed(entry.embedding_document)
        self._store.save_embedding(article_id, embedding)

        return ProductEmbeddingResult(
            article_id=article_id,
            status="recalculated" if entry.has_embedding else "embedded",
            model=getattr(provider, "model", None),
            dimensions=len(embedding),
        )
