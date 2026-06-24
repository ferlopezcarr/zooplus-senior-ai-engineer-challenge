from __future__ import annotations

import pytest

from src.features.chat.domain.model import Chat, Query, SiteId
from src.features.chat.infrastructure.output.http.errors import (
    CatalogDatabaseUnavailableError,
)
from src.features.chat.infrastructure.output.persistence.product_database_retriever import (
    ProductDatabaseRetriever,
)
from src.features.product.infrastructure.output.persistence.product_catalog_reader import (
    ProductCatalogVectorMatch,
)
from src.features.product.infrastructure.output.persistence.product_catalog_repository import (
    ProductCatalogRecord,
)


def _catalog_record(**overrides: object) -> ProductCatalogRecord:
    values: dict[str, object] = {
        "article_id": 0,
        "product_id": "product-0",
        "variant_id": "variant-0",
        "site_id": 1,
        "pet_type": "dog",
        "brands": "Brand",
        "product_name": "Product",
        "variant_name": "Variant",
        "summary": "summary",
        "description": "description",
    }
    values.update(overrides)
    return ProductCatalogRecord(**values)


def _vector_match(*, distance: float, **overrides: object) -> ProductCatalogVectorMatch:
    return ProductCatalogVectorMatch(
        record=_catalog_record(**overrides),
        distance=distance,
    )


def test_database_product_retriever_orders_results_by_lexical_score(
    monkeypatch,
) -> None:
    retriever = ProductDatabaseRetriever(
        "postgresql+psycopg://test_user:test_password@example.test:5432/catalog"
    )

    def _load_rows_for_site(
        site_id: int,
        query_terms: set[str],
    ) -> list[ProductCatalogRecord]:
        assert site_id == 1
        assert query_terms == {"dog", "ball", "fetch"}
        return [
            _catalog_record(
                article_id=4002,
                product_id="beta-ball",
                variant_id="beta-ball-1",
                product_name="Beta Ball",
                variant_name="Dog Toy",
                summary="ball for dog play",
                description="durable dog toy",
                brands="Beta",
            ),
            _catalog_record(
                article_id=4001,
                product_id="alpha-ball",
                variant_id="alpha-ball-1",
                product_name="Alpha Ball",
                variant_name="Dog Toy",
                summary="ball for dog play",
                description="light dog toy",
                brands="Alpha",
            ),
            _catalog_record(
                article_id=4000,
                product_id="omega-ball",
                variant_id="omega-ball-1",
                product_name="Omega Ball",
                variant_name="Dog Fetch",
                summary="ball for dog fetch",
                description="fetch toy",
                brands="Omega",
            ),
        ]

    monkeypatch.setattr(
        retriever._catalog_reader, "load_rows_for_site", _load_rows_for_site
    )

    results = retriever.retrieve(Chat(site_id=SiteId(1), query=Query("dog ball fetch")))

    assert [product.article_id for product in results] == [4000, 4001, 4002]
    assert [product.score for product in results] == [3.0, 2.0, 2.0]


def test_database_product_retriever_prefers_vector_results_and_tops_up_lexical(
    monkeypatch,
) -> None:
    class StubEmbeddingClient:
        def embed(self, text: str) -> list[float]:
            assert text == "env ball"
            return [0.1, 0.2]

    retriever = ProductDatabaseRetriever(
        "postgresql+psycopg://test_user:test_password@example.test:5432/catalog",
        embedding_client_factory=lambda: StubEmbeddingClient(),
    )

    def _load_vector_rows_for_site(
        site_id: int,
        embedding: list[float],
        *,
        limit: int,
    ) -> list[ProductCatalogVectorMatch]:
        assert site_id == 77
        assert embedding == [0.1, 0.2]
        assert limit == 3
        return [
            _vector_match(
                distance=0.1,
                article_id=2002,
                product_id="vector-ball",
                variant_id="vector-ball-1",
                product_name="Vector Ball",
                variant_name="Dog Toy",
                summary="semantic match",
                description="embedding hit",
                brands="Vector",
                site_id=77,
            )
        ]

    def _load_rows_for_site(
        site_id: int,
        query_terms: set[str],
    ) -> list[ProductCatalogRecord]:
        assert site_id == 77
        assert query_terms == {"env", "ball"}
        return [
            _catalog_record(
                article_id=2002,
                product_id="vector-ball",
                variant_id="vector-ball-1",
                product_name="Vector Ball",
                variant_name="Dog Toy",
                summary="semantic match",
                description="embedding hit",
                brands="Vector",
                site_id=77,
            ),
            _catalog_record(
                article_id=2001,
                product_id="env-only-product",
                variant_id="env-only-product-1",
                product_name="Env Only Ball",
                variant_name="Dog Toy",
                summary="ball for dog fetch",
                description="small override dataset row",
                brands="Env Brand",
                site_id=77,
            ),
        ]

    monkeypatch.setattr(
        retriever._catalog_reader,
        "load_vector_rows_for_site",
        _load_vector_rows_for_site,
    )
    monkeypatch.setattr(
        retriever._catalog_reader, "load_rows_for_site", _load_rows_for_site
    )

    results = retriever.retrieve(Chat(site_id=SiteId(77), query=Query("env ball")))

    assert [product.article_id for product in results] == [2002, 2001]
    assert results[0].score == pytest.approx(0.9)
    assert results[1].score == 2.0


def test_database_product_retriever_uses_minimum_vector_similarity_threshold(
    monkeypatch,
) -> None:
    class StubEmbeddingClient:
        def embed(self, text: str) -> list[float]:
            assert text == "dog ball"
            return [0.1, 0.2]

    retriever = ProductDatabaseRetriever(
        "postgresql+psycopg://test_user:test_password@example.test:5432/catalog",
        embedding_client_factory=lambda: StubEmbeddingClient(),
    )

    def _load_vector_rows_for_site(
        site_id: int,
        embedding: list[float],
        *,
        limit: int,
    ) -> list[ProductCatalogVectorMatch]:
        assert site_id == 1
        assert embedding == [0.1, 0.2]
        assert limit == 3
        return [
            _vector_match(
                distance=0.7,
                article_id=3001,
                product_id="vector-kept",
                variant_id="vector-kept-1",
                product_name="Vector Kept",
                variant_name="Toy",
                summary="semantic match",
                description="kept at threshold",
                brands="Vector",
            ),
            _vector_match(
                distance=0.71,
                article_id=3002,
                product_id="vector-dropped",
                variant_id="vector-dropped-1",
                product_name="Vector Dropped",
                variant_name="Toy",
                summary="weak semantic match",
                description="below threshold",
                brands="Vector",
            ),
        ]

    def _load_rows_for_site(
        site_id: int,
        query_terms: set[str],
    ) -> list[ProductCatalogRecord]:
        assert site_id == 1
        assert query_terms == {"dog", "ball"}
        return [
            _catalog_record(
                article_id=1001,
                product_id="dog-ball-1",
                variant_id="dog-ball-1-a",
                product_name="Dog Ball Pro",
                variant_name="Fetch Toy",
                summary="dog ball for fetch",
                description="exact lexical match",
                brands="Alpha",
            ),
        ]

    monkeypatch.setattr(
        retriever._catalog_reader,
        "load_vector_rows_for_site",
        _load_vector_rows_for_site,
    )
    monkeypatch.setattr(
        retriever._catalog_reader, "load_rows_for_site", _load_rows_for_site
    )

    results = retriever.retrieve(Chat(site_id=SiteId(1), query=Query("dog ball")))

    assert [product.article_id for product in results] == [3001, 1001]
    assert results[0].score == pytest.approx(0.3)
    assert results[1].score == 2.0


def test_database_product_retriever_falls_back_to_lexical_when_embedding_fails(
    monkeypatch, caplog
) -> None:
    class FailingEmbeddingClient:
        def embed(self, text: str) -> list[float]:
            assert text == "env ball"
            raise RuntimeError("embedding offline")

    retriever = ProductDatabaseRetriever(
        "postgresql+psycopg://test_user:test_password@example.test:5432/catalog",
        embedding_client_factory=lambda: FailingEmbeddingClient(),
    )

    def _load_rows_for_site(
        site_id: int,
        query_terms: set[str],
    ) -> list[ProductCatalogRecord]:
        assert site_id == 77
        assert query_terms == {"env", "ball"}
        return [
            _catalog_record(
                article_id=2001,
                product_id="env-only-product",
                variant_id="env-only-product-1",
                product_name="Env Only Ball",
                variant_name="Dog Toy",
                summary="ball for dog fetch",
                description="small override dataset row",
                brands="Env Brand",
                site_id=77,
            )
        ]

    monkeypatch.setattr(
        retriever._catalog_reader, "load_rows_for_site", _load_rows_for_site
    )
    caplog.set_level("WARNING")

    results = retriever.retrieve(Chat(site_id=SiteId(77), query=Query("env ball")))

    assert [product.article_id for product in results] == [2001]
    assert [record.getMessage() for record in caplog.records] == [
        "Vector retrieval failed; using lexical fallback. error=embedding offline"
    ]


def test_database_product_retriever_ignores_zero_similarity_vector_saturation(
    monkeypatch,
) -> None:
    class StubEmbeddingClient:
        def embed(self, text: str) -> list[float]:
            assert text == "dog ball"
            return [0.1, 0.2]

    retriever = ProductDatabaseRetriever(
        "postgresql+psycopg://test_user:test_password@example.test:5432/catalog",
        embedding_client_factory=lambda: StubEmbeddingClient(),
    )

    def _load_vector_rows_for_site(
        site_id: int,
        embedding: list[float],
        *,
        limit: int,
    ) -> list[ProductCatalogVectorMatch]:
        assert site_id == 1
        assert embedding == [0.1, 0.2]
        assert limit == 3
        return [
            _vector_match(
                distance=1.0,
                article_id=9001,
                product_id="noise-1",
                variant_id="noise-1-a",
                product_name="Noise One",
                variant_name="Toy",
                summary="irrelevant row",
                description="semantic miss",
                brands="Noise",
            ),
            _vector_match(
                distance=1.1,
                article_id=9002,
                product_id="noise-2",
                variant_id="noise-2-a",
                product_name="Noise Two",
                variant_name="Toy",
                summary="irrelevant row",
                description="semantic miss",
                brands="Noise",
            ),
            _vector_match(
                distance=1.4,
                article_id=9003,
                product_id="noise-3",
                variant_id="noise-3-a",
                product_name="Noise Three",
                variant_name="Toy",
                summary="irrelevant row",
                description="semantic miss",
                brands="Noise",
            ),
        ]

    def _load_rows_for_site(
        site_id: int,
        query_terms: set[str],
    ) -> list[ProductCatalogRecord]:
        assert site_id == 1
        assert query_terms == {"dog", "ball"}
        return [
            _catalog_record(
                article_id=1001,
                product_id="dog-ball-1",
                variant_id="dog-ball-1-a",
                product_name="Dog Ball Pro",
                variant_name="Fetch Toy",
                summary="dog ball for fetch",
                description="exact lexical match",
                brands="Alpha",
            ),
            _catalog_record(
                article_id=1002,
                product_id="dog-ball-2",
                variant_id="dog-ball-2-a",
                product_name="Dog Ball Mini",
                variant_name="Toy",
                summary="dog ball toy",
                description="second lexical match",
                brands="Beta",
            ),
        ]

    monkeypatch.setattr(
        retriever._catalog_reader,
        "load_vector_rows_for_site",
        _load_vector_rows_for_site,
    )
    monkeypatch.setattr(
        retriever._catalog_reader, "load_rows_for_site", _load_rows_for_site
    )

    results = retriever.retrieve(Chat(site_id=SiteId(1), query=Query("dog ball")))

    assert [product.article_id for product in results] == [1002, 1001]
    assert [product.score for product in results] == [2.0, 2.0]


def test_database_product_retriever_wraps_database_failures(monkeypatch) -> None:
    retriever = ProductDatabaseRetriever(
        "postgresql+psycopg://test_user:test_password@example.test:5432/catalog"
    )

    def _load_rows_for_site(
        site_id: int,
        query_terms: set[str],
    ) -> list[ProductCatalogRecord]:
        assert site_id == 1
        assert query_terms == {"dog", "food"}
        raise OSError("database offline")

    monkeypatch.setattr(
        retriever._catalog_reader, "load_rows_for_site", _load_rows_for_site
    )

    with pytest.raises(
        CatalogDatabaseUnavailableError,
        match="Catalog retrieval is unavailable",
    ):
        retriever.retrieve(Chat(site_id=SiteId(1), query=Query("dog food")))


def test_readiness_error_returns_none_when_validation_succeeds(monkeypatch) -> None:
    retriever = ProductDatabaseRetriever(
        "postgresql+psycopg://test_user:test_password@example.test:5432/catalog"
    )
    captured: dict[str, bool] = {"validated": False}

    def _validate_database() -> None:
        captured["validated"] = True

    monkeypatch.setattr(
        retriever._catalog_reader,
        "validate_database",
        _validate_database,
    )

    assert retriever.readiness_error() is None
    assert captured["validated"] is True


def test_readiness_error_returns_validation_failure(monkeypatch) -> None:
    retriever = ProductDatabaseRetriever(
        "postgresql+psycopg://test_user:test_password@example.test:5432/catalog"
    )

    def _validate_database() -> None:
        raise ValueError("invalid catalog credentials")

    monkeypatch.setattr(
        retriever._catalog_reader,
        "validate_database",
        _validate_database,
    )

    assert retriever.readiness_error() == "invalid catalog credentials"
