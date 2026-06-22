from __future__ import annotations

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa


revision = "20260622_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "product_catalog_entries",
        sa.Column("article_id", sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column("product_id", sa.Text(), nullable=False),
        sa.Column("variant_id", sa.Text(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("locale", sa.Text(), nullable=False),
        sa.Column("pet_type", sa.Text(), nullable=False),
        sa.Column("brands", sa.Text(), nullable=False),
        sa.Column("product_name", sa.Text(), nullable=False),
        sa.Column("variant_name", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("ingredients", sa.Text(), nullable=False),
        sa.Column("feeding_recommendations", sa.Text(), nullable=False),
        sa.Column("price", sa.Float(precision=53), nullable=True),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("embedding_document", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(), nullable=True),
    )
    op.create_index(
        "ix_product_catalog_entries_site_id",
        "product_catalog_entries",
        ["site_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_product_catalog_entries_site_id", table_name="product_catalog_entries"
    )
    op.drop_table("product_catalog_entries")
