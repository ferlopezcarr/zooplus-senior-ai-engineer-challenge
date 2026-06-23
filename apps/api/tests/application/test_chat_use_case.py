from __future__ import annotations

import logging
import pytest

from src.application.answer_generator import (
    DeterministicAnswerGenerator,
    LlmAnswerGenerator,
)
from src.application.model.response_context import ResponseContext
from src.application.use_case.chat_use_case import ChatUseCase
from src.domain.model import Chat, Product, Query, SiteId
from src.domain.service import normalize_text
from src.infrastructure.output.product_database_retriever import (
    DatabaseProductRetriever,
)


def _stub_retriever(products: list[Product]):
    class StubRetriever:
        def retrieve(self, chat: Chat) -> list[Product]:
            return products

    return StubRetriever()


def _database_retriever(rows: list[dict[str, object]]) -> DatabaseProductRetriever:
    retriever = DatabaseProductRetriever(
        "postgresql+psycopg://test_user:test_password@example.test:5432/catalog"
    )

    def _load_rows_for_site(
        site_id: int,
        query_terms: set[str],
    ) -> list[dict[str, object]]:
        del query_terms
        return [
            row
            for row in rows
            if isinstance(row["site_id"], int)
            and not isinstance(row["site_id"], bool)
            and row["site_id"] == site_id
        ]

    retriever._load_rows_for_site = _load_rows_for_site  # type: ignore[method-assign]
    return retriever


def test_query_value_object_rejects_blank_queries() -> None:
    with pytest.raises(ValueError, match="query"):
        Query("   ")


def test_query_value_object_rejects_queries_without_searchable_terms() -> None:
    with pytest.raises(ValueError, match="searchable"):
        Query("!!! &amp; ???")


def test_query_value_object_rejects_overlong_queries() -> None:
    with pytest.raises(ValueError, match="at most 500 characters"):
        Query("a" * 501)


def test_query_value_object_normalizes_html_and_punctuation() -> None:
    assert Query("Cats &amp; Dogs!!").value == "cats dogs"


def test_query_value_object_normalizes_once_for_retrieval_and_answer_generation() -> (
    None
):
    query = Query("¿Qué pelota para perro recomendás?  ")

    assert query.value == "qu pelota para perro recomend s"


def test_text_normalizer_service_normalizes_html_text_for_user_readable_output() -> (
    None
):
    assert normalize_text("Best <b>Fish</b> &amp; Chips") == "Best Fish & Chips"


def test_chat_use_case_refuses_off_topic_queries() -> None:
    use_case = ChatUseCase(_stub_retriever([]))

    result = use_case.handle(
        Chat(site_id=SiteId(1), query=Query("what is the weather today"))
    )

    assert result.retrieved_products == []
    assert "pet products" in result.answer.lower()


def test_chat_use_case_hides_retrieved_products_for_off_topic_queries() -> None:
    class SpyRetriever:
        def retrieve(self, chat: Chat) -> list[Product]:
            assert chat.query.value == "what is the weather today"
            return [
                Product(
                    article_id=5511354,
                    product_id="dog-ball",
                    variant_id="759837.1",
                    title="Env Only Ball - Dog Toy",
                    summary="ball for dog fetch",
                    site_id=77,
                    category="dog",
                    score=2.0,
                )
            ]

    retriever = SpyRetriever()
    use_case = ChatUseCase(retriever)

    result = use_case.handle(
        Chat(site_id=SiteId(1), query=Query("what is the weather today"))
    )

    assert result.retrieved_products == []
    assert "pet products" in result.answer.lower()


def test_chat_use_case_hides_retrieved_products_for_single_word_off_topic_queries() -> (
    None
):
    class SpyRetriever:
        def retrieve(self, chat: Chat) -> list[Product]:
            assert chat.query.value == "bitcoin"
            return [
                Product(
                    article_id=5511354,
                    product_id="dog-ball",
                    variant_id="759837.1",
                    title="Env Only Ball - Dog Toy",
                    summary="ball for dog fetch",
                    site_id=77,
                    category="dog",
                    score=2.0,
                )
            ]

    use_case = ChatUseCase(SpyRetriever())

    result = use_case.handle(Chat(site_id=SiteId(1), query=Query("bitcoin")))

    assert result.retrieved_products == []
    assert "pet products" in result.answer.lower()


def test_chat_use_case_keeps_retrieved_products_for_brand_only_queries() -> None:
    product = Product(
        article_id=3001,
        product_id="brand-only-product",
        variant_id="brand-only-product-1",
        title="Sensitive Dry Food",
        summary="complete nutrition",
        site_id=5,
        category="dog",
        score=1.0,
    )

    class StubRetriever:
        def retrieve(self, chat: Chat) -> list[Product]:
            assert chat.query.value == "eukanuba"
            return [
                Product(
                    article_id=product.article_id,
                    product_id=product.product_id,
                    variant_id=product.variant_id,
                    title=product.title,
                    summary=product.summary,
                    site_id=product.site_id,
                    category=product.category,
                    score=product.score,
                    search_text="eukanuba sensitive dry food complete nutrition dog",
                )
            ]

    use_case = ChatUseCase(StubRetriever())

    result = use_case.handle(Chat(site_id=SiteId(5), query=Query("eukanuba")))

    assert result.retrieved_products == [product]
    assert "catalog matches" in result.answer.lower()


def test_chat_use_case_reports_no_results_without_inventing_products() -> None:
    use_case = ChatUseCase(_stub_retriever([]))

    result = use_case.handle(Chat(site_id=SiteId(1), query=Query("hamster submarine")))

    assert result.retrieved_products == []
    assert "could not find" in result.answer.lower()
    assert "site 1" in result.answer.lower()


def test_chat_use_case_builds_answer_from_same_product_context_it_returns() -> None:
    product = Product(
        article_id=5511354,
        product_id="dog-ball",
        variant_id="759837.1",
        title="Env Only Ball - Dog Toy",
        summary="ball for dog fetch",
        site_id=77,
        category="dog",
        score=2.0,
    )

    class StubRetriever:
        def retrieve(self, chat: Chat) -> list[Product]:
            return [product]

    use_case = ChatUseCase(StubRetriever())

    result = use_case.handle(Chat(site_id=SiteId(77), query=Query("env ball")))

    assert result.retrieved_products == [product]
    assert result.answer == (
        "For site 77, I found these catalog matches: "
        "Env Only Ball - Dog Toy (dog): ball for dog fetch."
    )


def test_answer_generator_builds_catalog_answer_from_response_context() -> None:
    generator = DeterministicAnswerGenerator()
    context = ResponseContext(
        products=[
            Product(
                article_id=5511354,
                product_id="dog-ball",
                variant_id="759837.1",
                title="Env Only Ball - Dog Toy",
                summary="ball for dog fetch",
                site_id=77,
                category="dog",
                score=2.0,
            )
        ]
    )

    answer = generator.from_catalog(site_id=77, query="ignored", context=context)

    assert answer == (
        "For site 77, I found these catalog matches: "
        "Env Only Ball - Dog Toy (dog): ball for dog fetch."
    )


def test_llm_answer_generator_uses_llm_response_when_available() -> None:
    class StubLLMClient:
        def from_catalog(
            self, site_id: int, query: str, context: ResponseContext
        ) -> str:
            assert site_id == 77
            assert query == "qu pelota para perro recomend s"
            assert context.products[0].title == "Env Only Ball - Dog Toy"
            return "Grounded LLM answer"

    generator = LlmAnswerGenerator(StubLLMClient())
    context = ResponseContext(
        products=[
            Product(
                article_id=5511354,
                product_id="dog-ball",
                variant_id="759837.1",
                title="Env Only Ball - Dog Toy",
                summary="ball for dog fetch",
                site_id=77,
                category="dog",
                score=2.0,
            )
        ]
    )

    assert (
        generator.from_catalog(
            site_id=77,
            query="qu pelota para perro recomend s",
            context=context,
        )
        == "Grounded LLM answer"
    )


def test_llm_answer_generator_falls_back_to_deterministic_answer(caplog) -> None:
    class FailingLLMClient:
        def from_catalog(
            self, site_id: int, query: str, context: ResponseContext
        ) -> str:
            raise TimeoutError("boom")

    generator = LlmAnswerGenerator(FailingLLMClient())
    caplog.set_level(logging.WARNING)
    context = ResponseContext(
        products=[
            Product(
                article_id=5511354,
                product_id="dog-ball",
                variant_id="759837.1",
                title="Env Only Ball - Dog Toy",
                summary="ball for dog fetch",
                site_id=77,
                category="dog",
                score=2.0,
            )
        ]
    )

    assert generator.from_catalog(site_id=77, query="env ball", context=context) == (
        "For site 77, I found these catalog matches: "
        "Env Only Ball - Dog Toy (dog): ball for dog fetch."
    )
    assert [record.getMessage() for record in caplog.records] == [
        "LLM answer generation failed; using deterministic fallback. error=boom"
    ]
    assert all(record.exc_info is None for record in caplog.records)


def test_llm_answer_generator_logs_sanitized_provider_error(caplog) -> None:
    class FailingLLMClient:
        def from_catalog(
            self, site_id: int, query: str, context: ResponseContext
        ) -> str:
            raise RuntimeError(
                "LLM provider request failed with HTTP 400: "
                '{"error":{"message":"bad request","api_key":"[REDACTED]"}}'
            )

    generator = LlmAnswerGenerator(FailingLLMClient())
    caplog.set_level(logging.WARNING)
    context = ResponseContext(
        products=[
            Product(
                article_id=5511354,
                product_id="dog-ball",
                variant_id="759837.1",
                title="Env Only Ball - Dog Toy",
                summary="ball for dog fetch",
                site_id=77,
                category="dog",
                score=2.0,
            )
        ]
    )

    assert generator.from_catalog(site_id=77, query="env ball", context=context) == (
        "For site 77, I found these catalog matches: "
        "Env Only Ball - Dog Toy (dog): ball for dog fetch."
    )
    assert [record.getMessage() for record in caplog.records] == [
        "LLM answer generation failed; using deterministic fallback. "
        'error=LLM provider request failed with HTTP 400: {"error":{"message":"bad request","api_key":"[REDACTED]"}}'
    ]


@pytest.mark.parametrize("answer", ["", "   ", None, 123])
def test_llm_answer_generator_logs_when_empty_or_non_string_answer_falls_back(
    answer, caplog
) -> None:
    class StubLLMClient:
        def from_catalog(self, site_id: int, query: str, context: ResponseContext):
            return answer

    generator = LlmAnswerGenerator(StubLLMClient())
    caplog.set_level(logging.WARNING)
    context = ResponseContext(
        products=[
            Product(
                article_id=5511354,
                product_id="dog-ball",
                variant_id="759837.1",
                title="Env Only Ball - Dog Toy",
                summary="ball for dog fetch",
                site_id=77,
                category="dog",
                score=2.0,
            )
        ]
    )

    assert generator.from_catalog(site_id=77, query="env ball", context=context) == (
        "For site 77, I found these catalog matches: "
        "Env Only Ball - Dog Toy (dog): ball for dog fetch."
    )
    assert [record.getMessage() for record in caplog.records] == [
        "LLM returned an empty or non-string answer; using deterministic fallback."
    ]


def test_chat_use_case_passes_raw_query_into_answer_generation() -> None:
    product = Product(
        article_id=5511354,
        product_id="dog-ball",
        variant_id="759837.1",
        title="Env Only Ball - Dog Toy",
        summary="ball for dog fetch",
        site_id=77,
        category="dog",
        score=2.0,
    )

    class StubRetriever:
        def retrieve(self, chat: Chat) -> list[Product]:
            return [product]

    class StubAnswerGenerator:
        def from_catalog(
            self, site_id: int, query: str, context: ResponseContext
        ) -> str:
            assert site_id == 77
            assert query == "qu pelota para perro recomend s"
            assert context.products == [product]
            return "Grounded answer"

        def off_topic(self) -> str:
            return "off-topic"

        def no_results(self, site_id: int) -> str:
            return "no-results"

    use_case = ChatUseCase(StubRetriever(), answer_generator=StubAnswerGenerator())

    result = use_case.handle(
        Chat(site_id=SiteId(77), query=Query("¿Qué pelota para perro recomendás?"))
    )

    assert result.answer == "Grounded answer"
    assert result.retrieved_products == [product]


def test_database_retriever_keeps_results_isolated_by_site() -> None:
    retriever = _database_retriever(
        [
            {
                "article_id": 1001,
                "product_id": "site-three",
                "variant_id": "site-three-1",
                "product_name": "Eukanuba Adult",
                "variant_name": "3kg",
                "summary": "complete nutrition",
                "description": "eukanuba dog food",
                "pet_type": "dog",
                "brands": "Eukanuba",
                "site_id": 3,
            },
            {
                "article_id": 1002,
                "product_id": "site-fifteen",
                "variant_id": "site-fifteen-1",
                "product_name": "Eukanuba Adult",
                "variant_name": "15kg",
                "summary": "complete nutrition",
                "description": "eukanuba dog food",
                "pet_type": "dog",
                "brands": "Eukanuba",
                "site_id": 15,
            },
        ]
    )

    site_three_results = retriever.retrieve(
        Chat(site_id=SiteId(3), query=Query("eukanuba"))
    )
    site_fifteen_results = retriever.retrieve(
        Chat(site_id=SiteId(15), query=Query("eukanuba"))
    )

    assert site_three_results
    assert site_fifteen_results
    assert {product.site_id for product in site_three_results} == {3}
    assert {product.site_id for product in site_fifteen_results} == {15}
