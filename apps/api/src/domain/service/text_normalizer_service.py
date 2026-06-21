from __future__ import annotations

import html
import re

_NON_WORD_PATTERN = re.compile(r"[^a-z0-9]+")


def normalize_query(value: str) -> str:
    normalized = html.unescape(value).lower()
    normalized = _NON_WORD_PATTERN.sub(" ", normalized)
    return " ".join(normalized.split())
