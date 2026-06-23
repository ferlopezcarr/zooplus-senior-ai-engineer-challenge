from src.domain.model import Product
from src.domain.service.text_normalizer_service import normalize_query

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
    if len(normalized_terms) == 1:
        term = normalized_terms[0]
        return term not in _DOMAIN_TERMS and not any(
            term in product.search_text.split() for product in products
        )

    return not any(term in _DOMAIN_TERMS for term in normalized_terms)
