from __future__ import annotations

from pathlib import Path

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
from src.infrastructure.output.product_retriever import ProductRetriever


DATASET_PATH = Path(__file__).resolve().parents[4] / "data/product_catalog_dataset.json"


def test_query_value_object_rejects_blank_queries() -> None:
    with pytest.raises(ValueError, match="query"):
        Query("   ")


def test_query_value_object_rejects_queries_without_searchable_terms() -> None:
    with pytest.raises(ValueError, match="searchable"):
        Query("!!! &amp; ???")


def test_query_value_object_normalizes_html_and_punctuation() -> None:
    assert Query("Cats &amp; Dogs!!").value == "cats dogs"


def test_text_normalizer_service_normalizes_html_text_for_user_readable_output() -> (
    None
):
    assert normalize_text("Best <b>Fish</b> &amp; Chips") == "Best Fish & Chips"


def test_chat_use_case_refuses_off_topic_queries() -> None:
    use_case = ChatUseCase(ProductRetriever(DATASET_PATH))

    result = use_case.handle(
        Chat(site_id=SiteId(1), query=Query("what is the weather today"))
    )

    assert result.retrieved_products == []
    assert "pet products" in result.answer.lower()


def test_chat_use_case_reports_no_results_without_inventing_products() -> None:
    use_case = ChatUseCase(ProductRetriever(DATASET_PATH))

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

    answer = generator.from_catalog(site_id=77, context=context)

    assert answer == (
        "For site 77, I found these catalog matches: "
        "Env Only Ball - Dog Toy (dog): ball for dog fetch."
    )


def test_llm_answer_generator_uses_llm_response_when_available() -> None:
    class StubLLMClient:
        def from_catalog(self, site_id: int, context: ResponseContext) -> str:
            assert site_id == 77
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

    assert generator.from_catalog(site_id=77, context=context) == "Grounded LLM answer"


def test_llm_answer_generator_falls_back_to_deterministic_answer(caplog) -> None:
    class FailingLLMClient:
        def from_catalog(self, site_id: int, context: ResponseContext) -> str:
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

    assert generator.from_catalog(site_id=77, context=context) == (
        "For site 77, I found these catalog matches: "
        "Env Only Ball - Dog Toy (dog): ball for dog fetch."
    )
    assert [record.getMessage() for record in caplog.records] == [
        "LLM answer generation failed; using deterministic fallback. error=boom"
    ]
    assert all(record.exc_info is None for record in caplog.records)


def test_llm_answer_generator_logs_sanitized_provider_error(caplog) -> None:
    class FailingLLMClient:
        def from_catalog(self, site_id: int, context: ResponseContext) -> str:
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

    assert generator.from_catalog(site_id=77, context=context) == (
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
        def from_catalog(self, site_id: int, context: ResponseContext):
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

    assert generator.from_catalog(site_id=77, context=context) == (
        "For site 77, I found these catalog matches: "
        "Env Only Ball - Dog Toy (dog): ball for dog fetch."
    )
    assert [record.getMessage() for record in caplog.records] == [
        "LLM returned an empty or non-string answer; using deterministic fallback."
    ]


def test_product_retriever_keeps_results_isolated_by_site() -> None:
    retriever = ProductRetriever(DATASET_PATH)

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
