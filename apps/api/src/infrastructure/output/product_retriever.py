from __future__ import annotations

import json
from functools import cached_property
from pathlib import Path

from src.domain.model import Chat, Product
from src.domain.service.text_normalizer_service import normalize_query
from src.infrastructure.output.service import to_product


PRODUCT_SEARCHABLE_FIELDS = (
    "product_name",
    "variant_name",
    "summary",
    "description",
    "pet_type",
    "brands",
)

REQUIRED_ROW_FIELDS = (
    "article_id",
    "product_id",
    "variant_id",
    "product_name",
    "variant_name",
    "site_id",
)


class DatasetNotReadyError(RuntimeError):
    pass


class ProductRetriever:
    def __init__(self, dataset_path: Path) -> None:
        self._dataset_path = dataset_path

    @cached_property
    def _rows(self) -> list[dict[str, object]]:
        try:
            rows = json.loads(self._dataset_path.read_text())
        except FileNotFoundError as exc:
            raise DatasetNotReadyError(
                f"Catalog dataset is unavailable: file not found at {self._dataset_path}."
            ) from exc
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DatasetNotReadyError(
                f"Catalog dataset is unavailable: could not read valid JSON from {self._dataset_path}."
            ) from exc

        if not isinstance(rows, list):
            raise DatasetNotReadyError(
                "Catalog dataset is unavailable: root JSON value must be an array."
            )

        for index, row in enumerate(rows):
            self._validate_row(index, row)

        return rows

    def readiness_error(self) -> str | None:
        try:
            _ = self._rows
        except DatasetNotReadyError as exc:
            return str(exc)
        return None

    def retrieve(self, chat: Chat, limit: int = 3) -> list[Product]:
        query_terms = set(normalize_query(chat.query.value).split())
        if not query_terms:
            return []

        minimum_score = 1 if len(query_terms) == 1 else 2

        scored_matches: list[tuple[int, Product]] = []
        for row in self._rows:
            if not self._row_matches_site(row, chat.site_id.value):
                continue

            searchable_terms = self._build_searchable_terms(row)
            score = self._calculate_match_score(query_terms, searchable_terms)
            if score < minimum_score:
                continue
            scored_matches.append(
                (
                    score,
                    to_product(row, chat.site_id.value, float(score)),
                )
            )

        scored_matches.sort(key=lambda item: (-item[0], item[1].title))
        return [product for _, product in scored_matches[:limit]]

    def _row_matches_site(self, row: dict[str, object], site_id: int) -> bool:
        row_site_id = row.get("site_id")
        return (
            isinstance(row_site_id, int)
            and not isinstance(row_site_id, bool)
            and row_site_id == site_id
        )

    def _build_searchable_terms(self, row: dict[str, object]) -> set[str]:
        normalized_content = normalize_query(
            " ".join(str(row.get(field, "")) for field in PRODUCT_SEARCHABLE_FIELDS)
        )
        return set(normalized_content.split())

    def _calculate_match_score(
        self,
        query_terms: set[str],
        searchable_terms: set[str],
    ) -> int:
        return sum(1 for term in query_terms if term in searchable_terms)

    def _validate_row(self, index: int, row: object) -> None:
        if not isinstance(row, dict):
            raise DatasetNotReadyError(
                f"Catalog dataset is unavailable: row {index} must be a JSON object."
            )

        missing_fields = [field for field in REQUIRED_ROW_FIELDS if field not in row]
        if missing_fields:
            missing = ", ".join(missing_fields)
            raise DatasetNotReadyError(
                f"Catalog dataset is unavailable: row {index} is missing required fields: {missing}."
            )

        article_id = row.get("article_id")
        if not isinstance(article_id, int) or isinstance(article_id, bool):
            raise DatasetNotReadyError(
                f"Catalog dataset is unavailable: row {index} has an invalid article_id."
            )
