from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import create_engine, or_, select

from src.features.product.infrastructure.output.persistence.product_catalog_repository import (
    PRODUCT_SEARCHABLE_FIELDS,
    ProductCatalogRecord,
    product_catalog_entries,
    to_product_catalog_record,
)


LEXICAL_CANDIDATE_ROW_LIMIT = 200
MAX_SQL_PREFILTER_TERMS = 6
VECTOR_CANDIDATE_ROW_LIMIT = 6
MINIMUM_VECTOR_SIMILARITY = 0.3
MAXIMUM_VECTOR_DISTANCE = 1.0 - MINIMUM_VECTOR_SIMILARITY


@dataclass(frozen=True)
class ProductCatalogVectorMatch:
    record: ProductCatalogRecord
    distance: float


class ProductCatalogReader:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def validate_database(self) -> None:
        engine = create_engine(self._database_url)
        try:
            with engine.connect() as connection:
                connection.execute(
                    select(product_catalog_entries.c.article_id).limit(1)
                )
        finally:
            engine.dispose()

    def load_rows_for_site(
        self,
        site_id: int,
        query_terms: set[str],
    ) -> list[ProductCatalogRecord]:
        engine = create_engine(self._database_url)
        statement = self._build_candidate_statement(site_id, query_terms)

        try:
            with engine.connect() as connection:
                result = connection.execute(statement)
                return [to_product_catalog_record(row) for row in result.mappings()]
        finally:
            engine.dispose()

    def load_vector_rows_for_site(
        self,
        site_id: int,
        embedding: list[float],
        *,
        limit: int,
    ) -> list[ProductCatalogVectorMatch]:
        engine = create_engine(self._database_url)
        statement = self._build_vector_statement(site_id, embedding, limit=limit)

        try:
            with engine.connect() as connection:
                result = connection.execute(statement)
                return [
                    ProductCatalogVectorMatch(
                        record=to_product_catalog_record(row),
                        distance=float(row["distance"]),
                    )
                    for row in result.mappings()
                ]
        finally:
            engine.dispose()

    def _build_candidate_statement(self, site_id: int, query_terms: set[str]):
        statement = select(
            product_catalog_entries.c.article_id,
            product_catalog_entries.c.product_id,
            product_catalog_entries.c.variant_id,
            product_catalog_entries.c.site_id,
            product_catalog_entries.c.pet_type,
            product_catalog_entries.c.brands,
            product_catalog_entries.c.product_name,
            product_catalog_entries.c.variant_name,
            product_catalog_entries.c.summary,
            product_catalog_entries.c.description,
        ).where(product_catalog_entries.c.site_id == site_id)

        candidate_clauses = [
            product_catalog_entries.c[field].ilike(f"%{term}%")
            for term in _sql_prefilter_terms(query_terms)
            for field in PRODUCT_SEARCHABLE_FIELDS
        ]
        if candidate_clauses:
            statement = statement.where(or_(*candidate_clauses))

        return statement.order_by(product_catalog_entries.c.article_id.asc()).limit(
            LEXICAL_CANDIDATE_ROW_LIMIT
        )

    def _build_vector_statement(
        self,
        site_id: int,
        embedding: list[float],
        *,
        limit: int,
    ):
        distance = product_catalog_entries.c.embedding.cosine_distance(embedding)
        return (
            select(
                product_catalog_entries.c.article_id,
                product_catalog_entries.c.product_id,
                product_catalog_entries.c.variant_id,
                product_catalog_entries.c.site_id,
                product_catalog_entries.c.pet_type,
                product_catalog_entries.c.brands,
                product_catalog_entries.c.product_name,
                product_catalog_entries.c.variant_name,
                product_catalog_entries.c.summary,
                product_catalog_entries.c.description,
                distance.label("distance"),
            )
            .where(product_catalog_entries.c.site_id == site_id)
            .where(product_catalog_entries.c.embedding.is_not(None))
            .where(distance <= MAXIMUM_VECTOR_DISTANCE)
            .order_by(distance.asc(), product_catalog_entries.c.article_id.asc())
            .limit(min(limit, VECTOR_CANDIDATE_ROW_LIMIT))
        )


def _sql_prefilter_terms(query_terms: set[str]) -> tuple[str, ...]:
    return tuple(
        sorted(query_terms, key=lambda term: (-len(term), term))[
            :MAX_SQL_PREFILTER_TERMS
        ]
    )
