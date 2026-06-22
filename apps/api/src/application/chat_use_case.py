from __future__ import annotations

from src.application.response_context import ResponseContext
from src.application.services.topic_service import is_off_topic
from src.domain import Chat, ChatResult
from src.infrastructure.output.product_retriever import ProductRetriever


class ChatUseCase:
    def __init__(self, retriever: ProductRetriever) -> None:
        self._retriever = retriever

    def handle(self, chat: Chat) -> ChatResult:
        products = self._retriever.retrieve(chat)
        if products:
            context = ResponseContext(products=products)
            return ChatResult(
                answer=self._build_catalog_answer(chat.site_id.value, context),
                retrieved_products=context.products,
            )

        if is_off_topic(chat.query.value):
            return ChatResult(
                answer="I can only help with pet products that exist in the provided catalog.",
                retrieved_products=[],
            )

        return ChatResult(
            answer=f"I could not find relevant products for site {chat.site_id.value} in the provided catalog.",
            retrieved_products=[],
        )

    def _build_catalog_answer(self, site_id: int, context: ResponseContext) -> str:
        evidence = "; ".join(
            f"{product.title} ({product.category}): {product.summary}"
            for product in context.products
        )
        return f"For site {site_id}, I found these catalog matches: {evidence}."
