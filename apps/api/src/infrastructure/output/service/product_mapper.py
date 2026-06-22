from __future__ import annotations

from src.domain import Product
from src.domain.service.text_normalizer_service import normalize_text


def to_product(row: dict[str, object], site_id: int, score: float) -> Product:
    return Product(
        article_id=int(row["article_id"]),
        product_id=str(row["product_id"]),
        variant_id=str(row["variant_id"]),
        title=f"{row['product_name']} - {row['variant_name']}",
        summary=normalize_text(str(row.get("summary", ""))),
        site_id=site_id,
        category=str(row.get("pet_type", "")),
        score=score,
    )
