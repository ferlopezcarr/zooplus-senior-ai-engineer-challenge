from __future__ import annotations

from src.application.response_context import ResponseContext


class AnswerGenerator:
    def from_catalog(self, site_id: int, context: ResponseContext) -> str:
        evidence = "; ".join(
            f"{product.title} ({product.category}): {product.summary}"
            for product in context.products
        )
        return f"For site {site_id}, I found these catalog matches: {evidence}."

    def off_topic(self) -> str:
        return "I can only help with pet products that exist in the provided catalog."

    def no_results(self, site_id: int) -> str:
        return f"I could not find relevant products for site {site_id} in the provided catalog."
