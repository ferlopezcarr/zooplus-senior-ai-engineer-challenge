from __future__ import annotations

from dataclasses import dataclass

from src.domain.model.query import Query
from src.domain.model.site_id import SiteId


@dataclass(frozen=True)
class Chat:
    site_id: SiteId
    query: Query
