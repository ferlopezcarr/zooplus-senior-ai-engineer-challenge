from __future__ import annotations

from sqlalchemy.dialects import postgresql

import src.features.product.infrastructure.output.persistence.product_catalog_reader as reader_module
from src.features.product.infrastructure.output.persistence.product_catalog_reader import (
    LEXICAL_CANDIDATE_ROW_LIMIT,
    MAXIMUM_VECTOR_DISTANCE,
    MAX_SQL_PREFILTER_TERMS,
    ProductCatalogReader,
    VECTOR_CANDIDATE_ROW_LIMIT,
)
from src.features.product.infrastructure.output.persistence.product_catalog_repository import (
    PRODUCT_SEARCHABLE_FIELDS,
    build_product_search_text,
)


class _StubResult:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def mappings(self) -> list[dict[str, object]]:
        return self._rows


class _StubConnection:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows
        self.executed_statements: list[object] = []

    def __enter__(self) -> _StubConnection:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, statement):
        self.executed_statements.append(statement)
        return _StubResult(self._rows)


class _StubEngine:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.connection = _StubConnection(rows)
        self.disposed = False

    def connect(self) -> _StubConnection:
        return self.connection

    def dispose(self) -> None:
        self.disposed = True


def _install_engine(monkeypatch, rows: list[dict[str, object]]) -> _StubEngine:
    engine = _StubEngine(rows)
    monkeypatch.setattr(reader_module, "create_engine", lambda _: engine)
    return engine


def test_product_catalog_reader_validates_database_with_public_readiness_check(
    monkeypatch,
) -> None:
    engine = _install_engine(monkeypatch, rows=[])
    reader = ProductCatalogReader(
        "postgresql+psycopg://test_user:test_password@example.test:5432/catalog"
    )

    reader.validate_database()

    assert engine.disposed is True
    assert len(engine.connection.executed_statements) == 1

    compiled = engine.connection.executed_statements[0].compile(
        dialect=postgresql.dialect()
    )
    assert "SELECT product_catalog_entries.article_id" in str(compiled)
    assert "LIMIT %(param_1)s" in str(compiled)
    assert compiled.params["param_1"] == 1


def test_product_catalog_reader_loads_rows_for_site_via_public_method(
    monkeypatch,
) -> None:
    returned_rows = [
        {
            "article_id": 4001,
            "product_id": "alpha-ball",
            "variant_id": "alpha-ball-1",
            "site_id": 1,
            "pet_type": "dog",
            "brands": "Alpha",
            "product_name": "Alpha Ball",
            "variant_name": "Toy",
            "summary": "ball for dog play",
            "description": "durable dog toy",
        }
    ]
    engine = _install_engine(monkeypatch, rows=returned_rows)
    reader = ProductCatalogReader(
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

    rows = reader.load_rows_for_site(1, query_terms)

    assert rows == returned_rows
    assert engine.disposed is True
    assert len(engine.connection.executed_statements) == 1

    compiled = engine.connection.executed_statements[0].compile(
        dialect=postgresql.dialect()
    )
    assert compiled.params["site_id_1"] == 1
    assert compiled.params["param_1"] == LEXICAL_CANDIDATE_ROW_LIMIT
    assert "ORDER BY product_catalog_entries.article_id ASC" in str(compiled)
    assert "LIMIT %(param_1)s" in str(compiled)

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


def test_product_catalog_reader_loads_vector_rows_for_site_via_public_method(
    monkeypatch,
) -> None:
    returned_rows = [
        {
            "article_id": 2002,
            "product_id": "vector-ball",
            "variant_id": "vector-ball-1",
            "site_id": 77,
            "pet_type": "dog",
            "brands": "Vector",
            "product_name": "Vector Ball",
            "variant_name": "Dog Toy",
            "summary": "semantic match",
            "description": "embedding hit",
            "distance": 0.1,
        }
    ]
    engine = _install_engine(monkeypatch, rows=returned_rows)
    reader = ProductCatalogReader(
        "postgresql+psycopg://test_user:test_password@example.test:5432/catalog"
    )

    rows = reader.load_vector_rows_for_site(77, [0.1, 0.2], limit=9)

    assert rows == returned_rows
    assert engine.disposed is True
    assert len(engine.connection.executed_statements) == 1

    compiled = engine.connection.executed_statements[0].compile(
        dialect=postgresql.dialect()
    )

    assert compiled.params["site_id_1"] == 77
    assert compiled.params["embedding_1"] == [0.1, 0.2]
    assert compiled.params["param_1"] == MAXIMUM_VECTOR_DISTANCE
    assert compiled.params["param_2"] == VECTOR_CANDIDATE_ROW_LIMIT
    assert "embedding IS NOT NULL" in str(compiled)
    assert "<= %(param_1)s" in str(compiled)
    assert (
        "ORDER BY (product_catalog_entries.embedding <=> %(embedding_1)s) ASC"
        in str(compiled)
    )


def test_product_search_text_uses_canonical_fields() -> None:
    search_text = build_product_search_text(
        {
            "product_name": "Royal Canin",
            "variant_name": "Digestive Care",
            "summary": "Complete nutrition",
            "description": "For sensitive adult dogs",
            "pet_type": "dog",
            "brands": "Royal Canin",
            "ignored": "not included",
        }
    )

    assert PRODUCT_SEARCHABLE_FIELDS == (
        "product_name",
        "variant_name",
        "summary",
        "description",
        "pet_type",
        "brands",
    )
    assert search_text == (
        "royal canin digestive care complete nutrition "
        "for sensitive adult dogs dog royal canin"
    )
