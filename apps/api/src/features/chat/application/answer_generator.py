from __future__ import annotations

import logging
from typing import Protocol

from src.features.chat.application.answer_context import ResponseContext


LOGGER = logging.getLogger(__name__)


class AnswerGenerator(Protocol):
    def from_catalog(
        self, site_id: int, query: str, context: ResponseContext
    ) -> str: ...

    def off_topic(self) -> str: ...

    def no_results(self, site_id: int) -> str: ...


class DeterministicAnswerGenerator:
    def from_catalog(self, site_id: int, query: str, context: ResponseContext) -> str:
        return self._deterministic_from_catalog(site_id, context)

    def _deterministic_from_catalog(
        self, site_id: int, context: ResponseContext
    ) -> str:
        evidence = "; ".join(
            f"{product.title} ({product.category}): {product.summary}"
            for product in context.products
        )
        return f"For site {site_id}, I found these catalog matches: {evidence}."

    def off_topic(self) -> str:
        return "I can only help with pet products that exist in the provided catalog."

    def no_results(self, site_id: int) -> str:
        return f"I could not find relevant products for site {site_id} in the provided catalog."


class LlmAnswerGenerator:
    def __init__(self, llm_client) -> None:
        self._llm_client = llm_client
        self._fallback = DeterministicAnswerGenerator()

    def from_catalog(self, site_id: int, query: str, context: ResponseContext) -> str:
        fallback = self._fallback.from_catalog(site_id, query, context)

        try:
            answer = self._llm_client.from_catalog(site_id, query, context)
        except Exception as exc:
            LOGGER.warning(
                "LLM answer generation failed; using deterministic fallback. error=%s",
                exc,
            )
            return fallback

        if not isinstance(answer, str) or not answer.strip():
            LOGGER.warning(
                "LLM returned an empty or non-string answer; using deterministic fallback."
            )
            return fallback

        return answer.strip()

    def off_topic(self) -> str:
        return self._fallback.off_topic()

    def no_results(self, site_id: int) -> str:
        return self._fallback.no_results(site_id)
