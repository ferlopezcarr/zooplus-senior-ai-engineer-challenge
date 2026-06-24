from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy import create_engine, or_, select
from sqlalchemy.exc import SQLAlchemyError

from src.core.service.text_normalizer_service import normalize_query, normalize_text
from src.features.chat.domain.model import Chat, Product
from src.features.chat.infrastructure.output.http.errors import (
    CatalogDatabaseUnavailableError,
)
from src.features.product.infrastructure.output.persistence.product_catalog_repository import (
    PRODUCT_SEARCHABLE_FIELDS,
    ProductCatalogRecord,
    build_product_search_text,
    product_catalog_entries,
    to_product_catalog_record,
)


PRODUCT_CATALOG_DATABASE_URL_ENV = "PRODUCT_CATALOG_DATABASE_URL"
LEXICAL_CANDIDATE_ROW_LIMIT = 200
MAX_SQL_PREFILTER_TERMS = 6
VECTOR_CANDIDATE_ROW_LIMIT = 6
MINIMUM_VECTOR_SIMILARITY = 0.3
MAXIMUM_VECTOR_DISTANCE = 1.0 - MINIMUM_VECTOR_SIMILARITY
SINGLE_TERM_MINIMUM_MATCH_SCORE = 1
MULTI_TERM_MINIMUM_MATCH_SCORE = 2

LOGGER = logging.getLogger(__name__)


class DatabaseProductRetriever:
    def __init__(
        self,
        database_url: str,
        embedding_client_factory: Callable[[], object] | None = None,
    ) -> None:
        self._database_url = database_url
        self._embedding_client_factory = embedding_client_factory

    def readiness_error(self) -> str | None:
        try:
            self._validate_database()
        except (RuntimeError, SQLAlchemyError, OSError, ValueError) as exc:
            return str(exc)
        return None

    def retrieve(self, chat: Chat, limit: int = 3) -> list[Product]:
        query_terms = split_query_terms(chat.query.value)
        if not query_terms:
            return []

        vector_products = self._retrieve_vector_products(chat, limit=limit)
        if len(vector_products) >= limit:
            return vector_products

        try:
            rows = self._load_rows_for_site(chat.site_id.value, query_terms)
        except (RuntimeError, SQLAlchemyError, OSError, ValueError) as exc:
            raise CatalogDatabaseUnavailableError(
                "Catalog retrieval is unavailable."
            ) from exc

        ranked_rows = rank_rows_by_query_terms(
            rows, query_terms=query_terms, limit=limit
        )
        lexical_products = [
            _to_chat_product(to_product_catalog_record(row), float(score))
            for score, row in ranked_rows
        ]
        if not vector_products:
            return lexical_products

        seen_article_ids = {product.article_id for product in vector_products}
        lexical_top_up = [
            product
            for product in lexical_products
            if product.article_id not in seen_article_ids
        ]
        return (vector_products + lexical_top_up)[:limit]

    def _validate_database(self) -> None:
        engine = create_engine(self._database_url)
        try:
            with engine.connect() as connection:
                connection.execute(
                    select(product_catalog_entries.c.article_id).limit(1)
                )
        finally:
            engine.dispose()

    def _load_rows_for_site(
        self,
        site_id: int,
        query_terms: set[str],
    ) -> list[dict[str, object]]:
        engine = create_engine(self._database_url)
        statement = self._build_candidate_statement(site_id, query_terms)

        try:
            with engine.connect() as connection:
                result = connection.execute(statement)
                return [dict(row) for row in result.mappings()]
        finally:
            engine.dispose()

    def _retrieve_vector_products(self, chat: Chat, *, limit: int) -> list[Product]:
        if self._embedding_client_factory is None:
            return []

        try:
            client = self._embedding_client_factory()
            embedding = client.embed(chat.query.value)
            rows = self._load_vector_rows_for_site(
                chat.site_id.value,
                embedding,
                limit=limit,
            )
        except Exception as exc:
            LOGGER.warning(
                "Vector retrieval failed; using lexical fallback. error=%s",
                exc,
            )
            return []

        vector_products: list[Product] = []
        for row in rows:
            similarity = _vector_similarity_from_distance(float(row["distance"]))
            if similarity < MINIMUM_VECTOR_SIMILARITY:
                continue
            vector_products.append(
                _to_chat_product(to_product_catalog_record(row), similarity)
            )
        return vector_products

    def _load_vector_rows_for_site(
        self,
        site_id: int,
        embedding: list[float],
        *,
        limit: int,
    ) -> list[dict[str, object]]:
        engine = create_engine(self._database_url)
        statement = self._build_vector_statement(site_id, embedding, limit=limit)

        try:
            with engine.connect() as connection:
                result = connection.execute(statement)
                return [dict(row) for row in result.mappings()]
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


def split_query_terms(query: str) -> set[str]:
    return set(normalize_query(query).split())


def rank_rows_by_query_terms(
    rows: list[dict[str, object]],
    *,
    query_terms: set[str],
    limit: int,
) -> list[tuple[int, dict[str, object]]]:
    if not query_terms:
        return []

    minimum_score = _minimum_match_score_for_query_terms(query_terms)
    scored_matches: list[tuple[int, dict[str, object]]] = []
    for row in rows:
        searchable_terms = _build_searchable_terms(row)
        score = _calculate_match_score(query_terms, searchable_terms)
        if score < minimum_score:
            continue
        scored_matches.append((score, row))

    scored_matches.sort(key=lambda item: (-item[0], _row_title(item[1])))
    return scored_matches[:limit]


def _sql_prefilter_terms(query_terms: set[str]) -> tuple[str, ...]:
    return tuple(
        sorted(query_terms, key=lambda term: (-len(term), term))[
            :MAX_SQL_PREFILTER_TERMS
        ]
    )


def _minimum_match_score_for_query_terms(query_terms: set[str]) -> int:
    if len(query_terms) <= 1:
        return SINGLE_TERM_MINIMUM_MATCH_SCORE
    return MULTI_TERM_MINIMUM_MATCH_SCORE


def _build_searchable_terms(row: dict[str, object]) -> set[str]:
    return set(build_product_search_text(row).split())


def _calculate_match_score(query_terms: set[str], searchable_terms: set[str]) -> int:
    return sum(1 for term in query_terms if term in searchable_terms)


def _row_title(row: dict[str, object]) -> str:
    return normalize_text(
        " ".join(
            part
            for part in (
                str(row.get("product_name", "")),
                str(row.get("variant_name", "")),
            )
            if part
        )
    )


def _vector_similarity_from_distance(distance: float) -> float:
    return max(0.0, 1.0 - distance)


def _to_chat_product(record: ProductCatalogRecord, score: float) -> Product:
    return Product(
        article_id=record.article_id,
        product_id=record.product_id,
        variant_id=record.variant_id,
        title=normalize_text(record.title),
        summary=normalize_text(record.summary),
        site_id=record.site_id,
        category=normalize_text(record.pet_type),
        score=score,
        search_text=build_product_search_text(record),
    )
