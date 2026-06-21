from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SiteId:
    value: int

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise ValueError("site_id must be a positive integer")
