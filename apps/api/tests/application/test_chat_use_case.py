from __future__ import annotations

from pathlib import Path

import pytest

from src.application.chat_use_case import ChatUseCase
from src.domain import Chat, Product, Query, SiteId
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
