from __future__ import annotations

import asyncio
from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Column, MetaData, Table, Text, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine

from src.infrastructure.output.model.product_embedding_entry import (
    ProductEmbeddingEntry,
)
from src.infrastructure.output.model.error import (
    ProductEmbeddingEntryNotFoundError,
    ProductEmbeddingStoreError,
)


metadata = MetaData()

product_catalog_entries = Table(
    "product_catalog_entries",
    metadata,
    Column("article_id", BigInteger, primary_key=True),
    Column("embedding_document", Text, nullable=False),
    Column("embedding", Vector(), nullable=True),
)


class DatabaseProductEmbeddingStore:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def get_entry(self, article_id: int) -> ProductEmbeddingEntry | None:
        try:
            return asyncio.run(self._get_entry(article_id))
        except (RuntimeError, SQLAlchemyError, OSError, ValueError) as exc:
            raise ProductEmbeddingStoreError(
                "Product embedding maintenance is unavailable."
            ) from exc

    def save_embedding(self, article_id: int, embedding: list[float]) -> None:
        try:
            asyncio.run(self._save_embedding(article_id, embedding))
        except ProductEmbeddingEntryNotFoundError:
            raise
        except (RuntimeError, SQLAlchemyError, OSError, ValueError) as exc:
            raise ProductEmbeddingStoreError(
                "Product embedding maintenance is unavailable."
            ) from exc

    async def _get_entry(self, article_id: int) -> ProductEmbeddingEntry | None:
        engine = create_async_engine(self._database_url)
        statement = select(
            product_catalog_entries.c.article_id,
            product_catalog_entries.c.embedding_document,
            product_catalog_entries.c.embedding,
        ).where(product_catalog_entries.c.article_id == article_id)

        try:
            async with engine.connect() as connection:
                result = await connection.execute(statement)
                row = result.mappings().first()
        finally:
            await engine.dispose()

        if row is None:
            return None

        return ProductEmbeddingEntry(
            article_id=int(row["article_id"]),
            embedding_document=str(row["embedding_document"]),
            has_embedding=row["embedding"] is not None,
        )

    async def _save_embedding(self, article_id: int, embedding: list[float]) -> None:
        engine = create_async_engine(self._database_url)
        statement = (
            update(product_catalog_entries)
            .where(product_catalog_entries.c.article_id == article_id)
            .values(embedding=embedding)
        )

        try:
            async with engine.begin() as connection:
                result = await connection.execute(statement)
        finally:
            await engine.dispose()

        if result.rowcount != 1:
            raise ProductEmbeddingEntryNotFoundError("Product not found.")
