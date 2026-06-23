from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Column,
    Integer,
    MetaData,
    Table,
    Text,
    or_,
    select,
)
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from src.domain.model import Chat, Product
from src.domain.service.text_normalizer_service import normalize_query
from src.infrastructure.output.model.error import CatalogDatabaseUnavailableError
from src.infrastructure.output.service import to_product


PRODUCT_CATALOG_DATABASE_URL_ENV = "PRODUCT_CATALOG_DATABASE_URL"
LEXICAL_CANDIDATE_ROW_LIMIT = 200
MAX_SQL_PREFILTER_TERMS = 6
PRODUCT_SEARCHABLE_FIELDS = (
    "product_name",
    "variant_name",
    "summary",
    "description",
    "pet_type",
    "brands",
)
SINGLE_TERM_MINIMUM_MATCH_SCORE = 1
MULTI_TERM_MINIMUM_MATCH_SCORE = 2

metadata = MetaData()

product_catalog_entries = Table(
    "product_catalog_entries",
    metadata,
    Column("article_id", BigInteger, primary_key=True),
    Column("product_id", Text, nullable=False),
    Column("variant_id", Text, nullable=False),
    Column("site_id", Integer, nullable=False),
    Column("pet_type", Text, nullable=False),
    Column("brands", Text, nullable=False),
    Column("product_name", Text, nullable=False),
    Column("variant_name", Text, nullable=False),
    Column("summary", Text, nullable=False),
    Column("description", Text, nullable=False),
)


class DatabaseProductRetriever:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

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

        try:
            rows = self._load_rows_for_site(chat.site_id.value, query_terms)
        except (RuntimeError, SQLAlchemyError, OSError, ValueError) as exc:
            raise CatalogDatabaseUnavailableError(
                "Catalog retrieval is unavailable."
            ) from exc

        ranked_rows = rank_rows_by_query_terms(
            rows, query_terms=query_terms, limit=limit
        )
        return [
            to_product(row, chat.site_id.value, float(score))
            for score, row in ranked_rows
        ]

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
    normalized_content = normalize_query(
        " ".join(str(row.get(field, "")) for field in PRODUCT_SEARCHABLE_FIELDS)
    )
    return set(normalized_content.split())


def _calculate_match_score(query_terms: set[str], searchable_terms: set[str]) -> int:
    return sum(1 for term in query_terms if term in searchable_terms)


def _row_title(row: dict[str, object]) -> str:
    product_name = str(row.get("product_name", ""))
    variant_name = str(row.get("variant_name", ""))
    return f"{product_name} - {variant_name}"
