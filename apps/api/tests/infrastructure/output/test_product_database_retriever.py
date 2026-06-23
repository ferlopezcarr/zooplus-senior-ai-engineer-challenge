from __future__ import annotations

import pytest
from sqlalchemy.dialects import postgresql

from src.domain.model import Chat, Query, SiteId
from src.infrastructure.output.model.error import CatalogDatabaseUnavailableError
from src.infrastructure.output.product_database_retriever import (
    LEXICAL_CANDIDATE_ROW_LIMIT,
    MAX_SQL_PREFILTER_TERMS,
    DatabaseProductRetriever,
)


def test_database_product_retriever_orders_results_by_lexical_score(
    monkeypatch,
) -> None:
    retriever = DatabaseProductRetriever(
        "postgresql+psycopg://test_user:test_password@example.test:5432/catalog"
    )

    def _load_rows_for_site(
        site_id: int,
        query_terms: set[str],
    ) -> list[dict[str, object]]:
        assert site_id == 1
        assert query_terms == {"dog", "ball", "fetch"}
        return [
            {
                "article_id": 4002,
                "product_id": "beta-ball",
                "variant_id": "beta-ball-1",
                "product_name": "Beta Ball",
                "variant_name": "Dog Toy",
                "summary": "ball for dog play",
                "description": "durable dog toy",
                "pet_type": "dog",
                "brands": "Beta",
                "site_id": 1,
            },
            {
                "article_id": 4001,
                "product_id": "alpha-ball",
                "variant_id": "alpha-ball-1",
                "product_name": "Alpha Ball",
                "variant_name": "Dog Toy",
                "summary": "ball for dog play",
                "description": "light dog toy",
                "pet_type": "dog",
                "brands": "Alpha",
                "site_id": 1,
            },
            {
                "article_id": 4000,
                "product_id": "omega-ball",
                "variant_id": "omega-ball-1",
                "product_name": "Omega Ball",
                "variant_name": "Dog Fetch",
                "summary": "ball for dog fetch",
                "description": "fetch toy",
                "pet_type": "dog",
                "brands": "Omega",
                "site_id": 1,
            },
        ]

    monkeypatch.setattr(retriever, "_load_rows_for_site", _load_rows_for_site)

    results = retriever.retrieve(Chat(site_id=SiteId(1), query=Query("dog ball fetch")))

    assert [product.article_id for product in results] == [4000, 4001, 4002]
    assert [product.score for product in results] == [3.0, 2.0, 2.0]


def test_database_product_retriever_wraps_database_failures(monkeypatch) -> None:
    retriever = DatabaseProductRetriever(
        "postgresql+psycopg://test_user:test_password@example.test:5432/catalog"
    )

    def _load_rows_for_site(
        site_id: int,
        query_terms: set[str],
    ) -> list[dict[str, object]]:
        assert site_id == 1
        assert query_terms == {"dog", "food"}
        raise OSError("database offline")

    monkeypatch.setattr(retriever, "_load_rows_for_site", _load_rows_for_site)

    with pytest.raises(
        CatalogDatabaseUnavailableError,
        match="Catalog retrieval is unavailable",
    ):
        retriever.retrieve(Chat(site_id=SiteId(1), query=Query("dog food")))


def test_readiness_error_returns_none_when_validation_succeeds(monkeypatch) -> None:
    retriever = DatabaseProductRetriever(
        "postgresql+psycopg://test_user:test_password@example.test:5432/catalog"
    )
    captured: dict[str, bool] = {"validated": False}

    def _validate_database() -> None:
        captured["validated"] = True

    monkeypatch.setattr(retriever, "_validate_database", _validate_database)

    assert retriever.readiness_error() is None
    assert captured["validated"] is True


def test_readiness_error_returns_validation_failure(monkeypatch) -> None:
    retriever = DatabaseProductRetriever(
        "postgresql+psycopg://test_user:test_password@example.test:5432/catalog"
    )

    def _validate_database() -> None:
        raise ValueError("invalid catalog credentials")

    monkeypatch.setattr(retriever, "_validate_database", _validate_database)

    assert retriever.readiness_error() == "invalid catalog credentials"


def test_database_product_retriever_bounds_sql_candidates() -> None:
    retriever = DatabaseProductRetriever(
        "postgresql+psycopg://test_user:test_password@example.test:5432/catalog"
    )

    statement = retriever._build_candidate_statement(1, {"dog", "ball"})
    compiled = statement.compile(dialect=postgresql.dialect())

    assert compiled.params["site_id_1"] == 1
    assert compiled.params["param_1"] == LEXICAL_CANDIDATE_ROW_LIMIT
    assert compiled.params["product_name_1"] == "%ball%"
    assert compiled.params["product_name_2"] == "%dog%"
    assert "ORDER BY product_catalog_entries.article_id ASC" in str(compiled)
    assert "LIMIT %(param_1)s" in str(compiled)


def test_database_product_retriever_caps_sql_prefilter_terms() -> None:
    retriever = DatabaseProductRetriever(
        "postgresql+psycopg://test_user:test_password@example.test:5432/catalog"
    )

    query_terms = {
        "dog",
        "ball",
        "fetch",
        "durable",
        "chew",
        "indoor",
        "outdoor",
        "treat",
    }

    statement = retriever._build_candidate_statement(1, query_terms)
    compiled = statement.compile(dialect=postgresql.dialect())

    ilike_params = {
        key: value
        for key, value in compiled.params.items()
        if key.startswith("product_name_")
    }

    assert len(ilike_params) == MAX_SQL_PREFILTER_TERMS
    assert set(ilike_params.values()) == {
        "%durable%",
        "%outdoor%",
        "%indoor%",
        "%fetch%",
        "%ball%",
        "%treat%",
    }
