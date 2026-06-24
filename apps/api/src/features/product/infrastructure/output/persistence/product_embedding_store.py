from __future__ import annotations

from sqlalchemy import create_engine, select, update
from sqlalchemy.exc import SQLAlchemyError

from src.features.product.application.ports import ProductEmbeddingEntry
from src.features.product.infrastructure.output.http.errors import (
    ProductEmbeddingEntryNotFoundError,
    ProductEmbeddingStoreError,
)
from src.features.product.infrastructure.output.persistence.product_catalog_repository import (
    product_catalog_entries,
)


class DatabaseProductEmbeddingStore:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def get_entry(self, article_id: int) -> ProductEmbeddingEntry | None:
        try:
            return self._get_entry(article_id)
        except (RuntimeError, SQLAlchemyError, OSError, ValueError) as exc:
            raise ProductEmbeddingStoreError(
                "Product embedding maintenance is unavailable."
            ) from exc

    def save_embedding(self, article_id: int, embedding: list[float]) -> None:
        try:
            self._save_embedding(article_id, embedding)
        except ProductEmbeddingEntryNotFoundError:
            raise
        except (RuntimeError, SQLAlchemyError, OSError, ValueError) as exc:
            raise ProductEmbeddingStoreError(
                "Product embedding maintenance is unavailable."
            ) from exc

    def _get_entry(self, article_id: int) -> ProductEmbeddingEntry | None:
        engine = create_engine(self._database_url)
        statement = select(
            product_catalog_entries.c.article_id,
            product_catalog_entries.c.embedding_document,
            product_catalog_entries.c.embedding,
        ).where(product_catalog_entries.c.article_id == article_id)

        try:
            with engine.connect() as connection:
                result = connection.execute(statement)
                row = result.mappings().first()
        finally:
            engine.dispose()

        if row is None:
            return None

        return ProductEmbeddingEntry(
            article_id=int(row["article_id"]),
            embedding_document=str(row["embedding_document"]),
            has_embedding=row["embedding"] is not None,
        )

    def _save_embedding(self, article_id: int, embedding: list[float]) -> None:
        engine = create_engine(self._database_url)
        statement = (
            update(product_catalog_entries)
            .where(product_catalog_entries.c.article_id == article_id)
            .values(embedding=embedding)
        )

        try:
            with engine.begin() as connection:
                result = connection.execute(statement)
        finally:
            engine.dispose()

        if result.rowcount != 1:
            raise ProductEmbeddingEntryNotFoundError("Product not found.")
