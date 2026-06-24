from __future__ import annotations

from dataclasses import dataclass

from src.core.service.text_normalizer_service import normalize_query


MAX_QUERY_LENGTH = 500


@dataclass(frozen=True)
class Query:
    value: str

    def __post_init__(self) -> None:
        value = self.value.strip()
        if not value:
            raise ValueError("query must not be blank")
        if len(value) > MAX_QUERY_LENGTH:
            raise ValueError(f"query must be at most {MAX_QUERY_LENGTH} characters")
        normalized_value = normalize_query(value)
        if not normalized_value:
            raise ValueError("query must contain searchable terms")
        object.__setattr__(self, "value", normalized_value)
