from __future__ import annotations

from src.application.services.topic_service import is_off_topic
from src.domain import Chat, ChatResult
from src.infrastructure.output.product_retriever import ProductRetriever


class ChatUseCase:
    def __init__(self, retriever: ProductRetriever) -> None:
        self._retriever = retriever

    def handle(self, chat: Chat) -> ChatResult:
        products = self._retriever.retrieve(chat)
        if products:
            titles = self._get_product_titles(products)
            return ChatResult(
                answer=f"For site {chat.site_id.value}, I found these catalog matches: {titles}.",
                retrieved_products=products,
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

    def _get_product_titles(self, products: list) -> str:
        return ", ".join(product.title for product in products)
