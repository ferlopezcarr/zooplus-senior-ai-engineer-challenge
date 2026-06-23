from dataclasses import dataclass


@dataclass(frozen=True)
class ProductEmbeddingEntry:
    article_id: int
    embedding_document: str
    has_embedding: bool
