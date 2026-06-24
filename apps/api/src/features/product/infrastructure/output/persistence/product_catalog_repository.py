from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Column, Integer, MetaData, Table, Text

from src.core.service.text_normalizer_service import normalize_query


PRODUCT_SEARCHABLE_FIELDS = (
    "product_name",
    "variant_name",
    "summary",
    "description",
    "pet_type",
    "brands",
)

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
    Column("embedding_document", Text, nullable=False),
    Column("embedding", Vector(), nullable=True),
)


@dataclass(frozen=True)
class ProductCatalogRecord:
    article_id: int
    product_id: str
    variant_id: str
    site_id: int
    pet_type: str
    brands: str
    product_name: str
    variant_name: str
    summary: str
    description: str

    @property
    def title(self) -> str:
        return f"{self.product_name} - {self.variant_name}"


def to_product_catalog_record(row: Mapping[str, object]) -> ProductCatalogRecord:
    return ProductCatalogRecord(
        article_id=int(row["article_id"]),
        product_id=str(row["product_id"]),
        variant_id=str(row["variant_id"]),
        site_id=int(row["site_id"]),
        pet_type=str(row.get("pet_type", "")),
        brands=str(row.get("brands", "")),
        product_name=str(row.get("product_name", "")),
        variant_name=str(row.get("variant_name", "")),
        summary=str(row.get("summary", "")),
        description=str(row.get("description", "")),
    )


def build_product_search_text(row: Mapping[str, object] | ProductCatalogRecord) -> str:
    return normalize_query(" ".join(_product_searchable_field_values(row)))


def _product_searchable_field_values(
    row: Mapping[str, object] | ProductCatalogRecord,
) -> tuple[str, ...]:
    if isinstance(row, ProductCatalogRecord):
        return tuple(
            str(getattr(row, field, "")) for field in PRODUCT_SEARCHABLE_FIELDS
        )

    return tuple(str(row.get(field, "")) for field in PRODUCT_SEARCHABLE_FIELDS)
