from src.core.service.text_normalizer_service import normalize_query
from src.features.chat.domain.model.product import Product

_DOMAIN_TERMS = {
    "cat",
    "cats",
    "comida",
    "dog",
    "dogs",
    "food",
    "gato",
    "gatos",
    "hamster",
    "hamsters",
    "toy",
    "toys",
    "ball",
    "balls",
    "pelota",
    "pelotas",
    "treat",
    "treats",
    "brush",
    "litter",
    "pet",
    "pets",
    "perro",
    "perros",
    "puppy",
    "kitten",
}


def is_off_topic(query: str) -> bool:
    return not any(term in _DOMAIN_TERMS for term in normalize_query(query).split())


def should_suppress_retrieved_products(query: str, products: list[Product]) -> bool:
    normalized_terms = normalize_query(query).split()
    if _query_matches_product_search_text(normalized_terms, products):
        return False

    return not any(term in _DOMAIN_TERMS for term in normalized_terms)


def _query_matches_product_search_text(
    normalized_terms: list[str], products: list[Product]
) -> bool:
    if not normalized_terms:
        return False

    return any(
        all(term in product.search_text.split() for term in normalized_terms)
        for product in products
    )
