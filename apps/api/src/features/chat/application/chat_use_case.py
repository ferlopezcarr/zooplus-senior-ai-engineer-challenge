from __future__ import annotations

from src.features.chat.application.answer_context import ResponseContext
from src.features.chat.application.answer_generator import (
    AnswerGenerator,
    DeterministicAnswerGenerator,
)
from src.features.chat.application.ports import ProductRetrievalPort
from src.features.chat.domain.model import Chat, ChatResult
from src.features.chat.domain.off_topic_policy import (
    is_off_topic,
    should_suppress_retrieved_products,
)


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
        if products and should_suppress_retrieved_products(chat.query.value, products):
            return ChatResult(
                answer=self._answer_generator.off_topic(),
                retrieved_products=[],
            )

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
