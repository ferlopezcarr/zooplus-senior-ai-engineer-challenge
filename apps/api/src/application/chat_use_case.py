from __future__ import annotations

from src.application.answer_generator import AnswerGenerator
from src.application.response_context import ResponseContext
from src.application.services.topic_service import is_off_topic
from src.domain import Chat, ChatResult
from src.infrastructure.output.product_retriever import ProductRetriever


class ChatUseCase:
    def __init__(
        self,
        retriever: ProductRetriever,
        answer_generator: AnswerGenerator | None = None,
    ) -> None:
        self._retriever = retriever
        self._answer_generator = answer_generator or AnswerGenerator()

    def handle(self, chat: Chat) -> ChatResult:
        products = self._retriever.retrieve(chat)
        if products:
            context = ResponseContext(products=products)
            return ChatResult(
                answer=self._answer_generator.from_catalog(chat.site_id.value, context),
                retrieved_products=context.products,
            )

        if is_off_topic(chat.query.value):
            return ChatResult(
                answer=self._answer_generator.off_topic(),
                retrieved_products=[],
            )

        return ChatResult(
            answer=self._answer_generator.no_results(chat.site_id.value),
            retrieved_products=[],
        )
