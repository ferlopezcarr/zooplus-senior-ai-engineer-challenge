from src.domain.service.text_normalizer_service import normalize_query

_DOMAIN_TERMS = {
    "cat",
    "cats",
    "dog",
    "dogs",
    "food",
    "hamster",
    "hamsters",
    "toy",
    "toys",
    "ball",
    "balls",
    "treat",
    "treats",
    "brush",
    "litter",
    "pet",
    "pets",
    "puppy",
    "kitten",
}


def is_off_topic(query: str) -> bool:
    return not any(term in _DOMAIN_TERMS for term in normalize_query(query).split())
