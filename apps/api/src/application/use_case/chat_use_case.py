from __future__ import annotations

from src.application.answer_generator import (
    AnswerGenerator,
    DeterministicAnswerGenerator,
)
from src.application.model.response_context import ResponseContext
from src.application.service.topic_service import is_off_topic
from src.domain.model import Chat, ChatResult
from src.infrastructure.output.product_retrieval_port import ProductRetrievalPort


class ChatUseCase:
    def __init__(
        self,
        retriever: ProductRetrievalPort,
        answer_generator: AnswerGenerator | None = None,
    ) -> None:
        self._retriever = retriever
        self._answer_generator = answer_generator or DeterministicAnswerGenerator()

    def handle(self, chat: Chat) -> ChatResult:
        products = self._retriever.retrieve(chat)
        if products:
            context = ResponseContext(products=products)
            return ChatResult(
                answer=self._answer_generator.from_catalog(
                    chat.site_id.value,
                    chat.query.value,
                    context,
                ),
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
