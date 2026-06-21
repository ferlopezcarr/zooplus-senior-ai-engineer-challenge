from __future__ import annotations

from dataclasses import dataclass

from src.domain.query import Query
from src.domain.site_id import SiteId


@dataclass(frozen=True)
class Chat:
    site_id: SiteId
    query: Query
