from __future__ import annotations

import pytest

from src.features.product.application.ports import ProductEmbeddingEntry
from src.features.product.application.product_embedding_use_case import (
    ProductEmbeddingNotFoundError,
    ProductEmbeddingUseCase,
)


class StubEmbeddingStore:
    def __init__(self, entry: ProductEmbeddingEntry | None) -> None:
        self.entry = entry
        self.saved_article_id: int | None = None
        self.saved_embedding: list[float] | None = None

    def get_entry(self, article_id: int) -> ProductEmbeddingEntry | None:
        if self.entry is None:
            return None

        assert article_id == self.entry.article_id
        return self.entry

    def save_embedding(self, article_id: int, embedding: list[float]) -> None:
        self.saved_article_id = article_id
        self.saved_embedding = embedding


def test_product_embedding_use_case_raises_not_found_when_entry_is_missing() -> None:
    use_case = ProductEmbeddingUseCase(
        store=StubEmbeddingStore(None),
        embedding_provider_factory=lambda: None,
    )

    with pytest.raises(ProductEmbeddingNotFoundError, match="Product not found"):
        use_case.handle(5511354, force=False)


def test_product_embedding_use_case_skips_provider_when_embedding_exists() -> None:
    calls = {"count": 0}

    class FailingProvider:
        model = "unused-model"

        def embed(self, text: str) -> list[float]:
            raise AssertionError("provider should not be called")

    def build_provider() -> FailingProvider:
        calls["count"] += 1
        return FailingProvider()

    store = StubEmbeddingStore(
        ProductEmbeddingEntry(
            article_id=5511354,
            embedding_document="Dog food for sensitive digestion.",
            has_embedding=True,
        )
    )
    use_case = ProductEmbeddingUseCase(
        store=store,
        embedding_provider_factory=build_provider,
    )

    result = use_case.handle(5511354, force=False)

    assert result.article_id == 5511354
    assert result.status == "already_embedded"
    assert result.model is None
    assert result.dimensions is None
    assert calls["count"] == 0
    assert store.saved_article_id is None
    assert store.saved_embedding is None


def test_product_embedding_use_case_generates_and_saves_missing_embedding() -> None:
    captured = {"document": None}

    class StubProvider:
        model = "test-embedding-model"

        def embed(self, text: str) -> list[float]:
            captured["document"] = text
            return [0.1, 0.2, 0.3]

    store = StubEmbeddingStore(
        ProductEmbeddingEntry(
            article_id=5511354,
            embedding_document="Dog food for sensitive digestion.",
            has_embedding=False,
        )
    )
    use_case = ProductEmbeddingUseCase(
        store=store,
        embedding_provider_factory=StubProvider,
    )

    result = use_case.handle(5511354, force=False)

    assert result.article_id == 5511354
    assert result.status == "embedded"
    assert result.model == "test-embedding-model"
    assert result.dimensions == 3
    assert captured["document"] == "Dog food for sensitive digestion."
    assert store.saved_article_id == 5511354
    assert store.saved_embedding == [0.1, 0.2, 0.3]


def test_product_embedding_use_case_recalculates_when_forced() -> None:
    calls = {"count": 0}

    class StubProvider:
        model = "test-embedding-model"

        def embed(self, text: str) -> list[float]:
            calls["count"] += 1
            return [0.9, 0.8]

    store = StubEmbeddingStore(
        ProductEmbeddingEntry(
            article_id=5511354,
            embedding_document="Dog food for sensitive digestion.",
            has_embedding=True,
        )
    )
    use_case = ProductEmbeddingUseCase(
        store=store,
        embedding_provider_factory=StubProvider,
    )

    result = use_case.handle(5511354, force=True)

    assert result.article_id == 5511354
    assert result.status == "recalculated"
    assert result.model == "test-embedding-model"
    assert result.dimensions == 2
    assert calls["count"] == 1
    assert store.saved_article_id == 5511354
    assert store.saved_embedding == [0.9, 0.8]
