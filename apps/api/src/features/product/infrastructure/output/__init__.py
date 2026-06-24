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
    "OpenAICompatibleEmbeddingClient",
    "PRODUCT_SEARCHABLE_FIELDS",
    "ProductEmbeddingEntryNotFoundError",
    "ProductCatalogRecord",
    "ProductEmbeddingStoreError",
    "build_product_search_text",
    "build_embeddings_url",
    "product_catalog_entries",
    "to_product_catalog_record",
]
