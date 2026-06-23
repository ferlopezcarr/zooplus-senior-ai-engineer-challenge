from __future__ import annotations

from os import getenv
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Column,
    Integer,
    MetaData,
    Table,
    Text,
    engine_from_config,
)
from sqlalchemy import pool
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION


config = context.config
PRODUCT_CATALOG_DATABASE_URL_ENV = "PRODUCT_CATALOG_DATABASE_URL"
DOTENV_PATH = Path(__file__).resolve().parents[1] / ".env"

metadata = MetaData()
Table(
    "product_catalog_entries",
    metadata,
    Column("article_id", BigInteger, primary_key=True),
    Column("product_id", Text, nullable=False),
    Column("variant_id", Text, nullable=False),
    Column("site_id", Integer, nullable=False, index=True),
    Column("locale", Text, nullable=False),
    Column("pet_type", Text, nullable=False),
    Column("brands", Text, nullable=False),
    Column("product_name", Text, nullable=False),
    Column("variant_name", Text, nullable=False),
    Column("summary", Text, nullable=False),
    Column("description", Text, nullable=False),
    Column("ingredients", Text, nullable=False),
    Column("feeding_recommendations", Text, nullable=False),
    Column("price", DOUBLE_PRECISION, nullable=True),
    Column("currency", Text, nullable=False),
    Column("embedding_document", Text, nullable=False),
    Column("embedding", Vector(), nullable=True),
)


def load_product_catalog_env(dotenv_path: Path | None = None) -> Path:
    resolved_dotenv_path = dotenv_path or DOTENV_PATH
    load_dotenv(resolved_dotenv_path)
    return resolved_dotenv_path


def get_product_catalog_database_url() -> str:
    value = getenv(PRODUCT_CATALOG_DATABASE_URL_ENV)
    if value is None or not value.strip():
        raise ValueError(
            f"{PRODUCT_CATALOG_DATABASE_URL_ENV} must be set for database commands."
        )

    return value.strip()


load_product_catalog_env()
config.set_main_option("sqlalchemy.url", get_product_catalog_database_url())
target_metadata = metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        do_run_migrations(connection)

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
