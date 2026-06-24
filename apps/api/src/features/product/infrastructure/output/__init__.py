from src.features.product.infrastructure.output.http.embedding_client import (
    DEFAULT_EMBEDDING_TIMEOUT_SECONDS,
    OpenAICompatibleEmbeddingClient,
    build_embeddings_url,
)
from src.features.product.infrastructure.output.http.errors import (
    EmbeddingConfigurationError,
    EmbeddingProviderHttpError,
    ProductEmbeddingEntryNotFoundError,
    ProductEmbeddingStoreError,
)
from src.features.product.infrastructure.output.persistence.product_catalog_reader import (
    LEXICAL_CANDIDATE_ROW_LIMIT,
    MAX_SQL_PREFILTER_TERMS,
    MINIMUM_VECTOR_SIMILARITY,
    ProductCatalogReader,
    VECTOR_CANDIDATE_ROW_LIMIT,
)
from src.features.product.infrastructure.output.persistence.product_embedding_store import (
    DatabaseProductEmbeddingStore,
)
from src.features.product.infrastructure.output.persistence.product_catalog_repository import (
    PRODUCT_SEARCHABLE_FIELDS,
    ProductCatalogRecord,
    build_product_search_text,
    product_catalog_entries,
    to_product_catalog_record,
)

__all__ = [
    "DEFAULT_EMBEDDING_TIMEOUT_SECONDS",
    "DatabaseProductEmbeddingStore",
    "EmbeddingConfigurationError",
    "EmbeddingProviderHttpError",
    "LEXICAL_CANDIDATE_ROW_LIMIT",
    "MAX_SQL_PREFILTER_TERMS",
    "MINIMUM_VECTOR_SIMILARITY",
    "OpenAICompatibleEmbeddingClient",
    "PRODUCT_SEARCHABLE_FIELDS",
    "ProductEmbeddingEntryNotFoundError",
    "ProductCatalogReader",
    "ProductCatalogRecord",
    "ProductEmbeddingStoreError",
    "VECTOR_CANDIDATE_ROW_LIMIT",
    "build_product_search_text",
    "build_embeddings_url",
    "product_catalog_entries",
    "to_product_catalog_record",
]
