# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import sys
from os import getenv
from pathlib import Path

from dotenv import load_dotenv
from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Column, Integer, MetaData, Table, Text, create_engine
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION, insert

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from src.core.service.text_normalizer_service import normalize_text


PRODUCT_CATALOG_DATABASE_URL_ENV = "PRODUCT_CATALOG_DATABASE_URL"
REPOSITORY_ROOT = API_ROOT.parent.parent
DOTENV_PATH = API_ROOT / ".env"
DEFAULT_DATASET_PATH = REPOSITORY_ROOT / "data/product_catalog_dataset.json"

metadata = MetaData()

product_catalog_entries = Table(
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load the product dataset into PostgreSQL for upcoming vector retrieval."
    )
    parser.add_argument(
        "--dataset-path",
        type=Path,
        default=DEFAULT_DATASET_PATH,
        help="Path to the product dataset JSON file.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and map the dataset without touching the database.",
    )
    return parser.parse_args()


def load_catalog_rows(dataset_path: Path) -> list[dict[str, object]]:
    rows = json.loads(dataset_path.read_text())
    if not isinstance(rows, list):
        raise ValueError("Catalog dataset root JSON value must be an array.")

    catalog_rows = [build_catalog_record(row, index) for index, row in enumerate(rows)]
    return deduplicate_catalog_rows(catalog_rows)


def build_catalog_record(row: object, index: int) -> dict[str, object]:
    if not isinstance(row, dict):
        raise ValueError(f"Catalog dataset row {index} must be a JSON object.")

    return {
        "article_id": _require_int(row, "article_id", index),
        "product_id": _require_text(row, "product_id", index),
        "variant_id": _require_text(row, "variant_id", index),
        "site_id": _require_int(row, "site_id", index),
        "locale": _optional_text(row, "locale"),
        "pet_type": _optional_text(row, "pet_type"),
        "brands": _optional_text(row, "brands"),
        "product_name": _require_text(row, "product_name", index),
        "variant_name": _require_text(row, "variant_name", index),
        "summary": _optional_text(row, "summary"),
        "description": _optional_text(row, "description"),
        "ingredients": _optional_text(row, "ingredients"),
        "feeding_recommendations": _optional_text(row, "feeding_recommendations"),
        "price": _optional_float(row, "price", index),
        "currency": _optional_text(row, "currency"),
        "embedding_document": build_embedding_document(row),
    }


def build_embedding_document(row: dict[str, object]) -> str:
    parts = [
        _optional_text(row, "product_name"),
        _optional_text(row, "variant_name"),
        _optional_text(row, "brands"),
        _optional_text(row, "pet_type"),
        _optional_text(row, "summary"),
        _optional_text(row, "description"),
        _optional_text(row, "ingredients"),
        _optional_text(row, "feeding_recommendations"),
    ]
    normalized_parts = [normalize_text(part) for part in parts if part.strip()]
    return "\n".join(normalized_parts)


def deduplicate_catalog_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    deduplicated_rows: dict[int, dict[str, object]] = {}

    for row in rows:
        article_id = int(row["article_id"])
        existing_row = deduplicated_rows.get(article_id)
        if existing_row is None:
            deduplicated_rows[article_id] = dict(row)
            continue

        deduplicated_rows[article_id] = merge_catalog_rows(existing_row, row)

    return list(deduplicated_rows.values())


def merge_catalog_rows(
    existing_row: dict[str, object],
    incoming_row: dict[str, object],
) -> dict[str, object]:
    if existing_row == incoming_row:
        return existing_row

    conflicting_fields = [
        field
        for field in existing_row
        if field not in {"pet_type", "embedding_document"}
        and existing_row[field] != incoming_row.get(field)
    ]
    if conflicting_fields:
        conflicting_field_names = ", ".join(sorted(conflicting_fields))
        raise ValueError(
            "Catalog dataset contains conflicting duplicate article rows for "
            f"article_id={existing_row['article_id']}: {conflicting_field_names}."
        )

    merged_row = dict(existing_row)
    merged_row["pet_type"] = merge_pet_types(
        str(existing_row.get("pet_type", "")),
        str(incoming_row.get("pet_type", "")),
    )
    merged_row["embedding_document"] = build_embedding_document(merged_row)
    return merged_row


def merge_pet_types(existing_value: str, incoming_value: str) -> str:
    pet_types: list[str] = []
    for value in (existing_value, incoming_value):
        normalized_value = value.strip()
        if normalized_value and normalized_value not in pet_types:
            pet_types.append(normalized_value)

    return " / ".join(pet_types)


def upsert_catalog_rows(rows: list[dict[str, object]]) -> int:
    engine = create_engine(get_product_catalog_database_url())
    upsert_statement = build_catalog_upsert_statement(rows)

    with engine.begin() as connection:
        connection.execute(upsert_statement)

    engine.dispose()
    return len(rows)


def build_catalog_upsert_statement(rows: list[dict[str, object]]):
    statement = insert(product_catalog_entries).values(rows)
    return statement.on_conflict_do_update(
        index_elements=[product_catalog_entries.c.article_id],
        set_={
            column.name: getattr(statement.excluded, column.name)
            for column in product_catalog_entries.columns
            if column.name not in {"article_id", "embedding"}
        },
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


def main() -> None:
    load_product_catalog_env()
    args = parse_args()
    rows = load_catalog_rows(args.dataset_path)

    if args.dry_run:
        print(
            f"Dry run ok: mapped {len(rows)} unique product rows from {args.dataset_path}."
        )
        return

    inserted_rows = upsert_catalog_rows(rows)
    print(f"Upserted {inserted_rows} product rows into PostgreSQL.")


def _require_int(row: dict[str, object], field: str, index: int) -> int:
    value = row.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"Catalog dataset row {index} has an invalid {field}.")
    return value


def _require_text(row: dict[str, object], field: str, index: int) -> str:
    if field not in row:
        raise ValueError(
            f"Catalog dataset row {index} is missing required field {field}."
        )

    return str(row[field])


def _optional_text(row: dict[str, object], field: str) -> str:
    value = row.get(field, "")
    return "" if value is None else str(value)


def _optional_float(row: dict[str, object], field: str, index: int) -> float | None:
    value = row.get(field)
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError(f"Catalog dataset row {index} has an invalid {field}.")
    return float(value)


if __name__ == "__main__":
    main()
