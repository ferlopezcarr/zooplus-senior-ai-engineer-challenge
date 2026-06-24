from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy.exc import SQLAlchemyError

from src.core.service.text_normalizer_service import normalize_query, normalize_text
from src.features.chat.domain.model import Chat, Product
from src.features.chat.infrastructure.output.http.errors import (
    CatalogDatabaseUnavailableError,
)
from src.features.product.infrastructure.output.persistence.product_catalog_reader import (
    MINIMUM_VECTOR_SIMILARITY,
    ProductCatalogReader,
)
from src.features.product.infrastructure.output.persistence.product_catalog_repository import (
    ProductCatalogRecord,
    build_product_search_text,
    to_product_catalog_record,
)


PRODUCT_CATALOG_DATABASE_URL_ENV = "PRODUCT_CATALOG_DATABASE_URL"
SINGLE_TERM_MINIMUM_MATCH_SCORE = 1
MULTI_TERM_MINIMUM_MATCH_SCORE = 2

LOGGER = logging.getLogger(__name__)


class ProductDatabaseRetriever:
    def __init__(
        self,
        database_url: str,
        embedding_client_factory: Callable[[], object] | None = None,
    ) -> None:
        self._catalog_reader = ProductCatalogReader(database_url)
        self._embedding_client_factory = embedding_client_factory

    def readiness_error(self) -> str | None:
        try:
            self._catalog_reader.validate_database()
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
            rows = self._catalog_reader.load_rows_for_site(
                chat.site_id.value,
                query_terms,
            )
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

    def _retrieve_vector_products(self, chat: Chat, *, limit: int) -> list[Product]:
        if self._embedding_client_factory is None:
            return []

        try:
            client = self._embedding_client_factory()
            embedding = client.embed(chat.query.value)
            rows = self._catalog_reader.load_vector_rows_for_site(
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
