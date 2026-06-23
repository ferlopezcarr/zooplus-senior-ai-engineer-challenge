from __future__ import annotations

import pytest

from src.infrastructure.output.model.error import (
    ProductEmbeddingEntryNotFoundError,
)
from src.infrastructure.output.product_embedding_store import (
    DatabaseProductEmbeddingStore,
)


def test_save_embedding_preserves_not_found_error(monkeypatch) -> None:
    store = DatabaseProductEmbeddingStore(
        "postgresql+psycopg://test_user:test_password@example.test:5432/catalog"
    )

    def _raise_not_found(article_id: int, embedding: list[float]) -> None:
        assert article_id == 5511354
        assert embedding == [0.1, 0.2]
        raise ProductEmbeddingEntryNotFoundError("Product not found.")

    monkeypatch.setattr(store, "_save_embedding", _raise_not_found)

    with pytest.raises(ProductEmbeddingEntryNotFoundError, match="Product not found"):
        store.save_embedding(5511354, [0.1, 0.2])
