from __future__ import annotations

from src.domain import Product


def to_product(row: dict[str, object], site_id: int, score: float) -> Product:
    return Product(
        product_id=str(row["product_id"]),
        title=f"{row['product_name']} - {row['variant_name']}",
        site_id=site_id,
        category=str(row.get("pet_type", "")),
        score=score,
    )
