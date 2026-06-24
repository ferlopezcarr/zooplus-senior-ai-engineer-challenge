class EmbeddingConfigurationError(RuntimeError):
    pass


class EmbeddingProviderHttpError(RuntimeError):
    pass


class ProductEmbeddingStoreError(RuntimeError):
    pass


class ProductEmbeddingEntryNotFoundError(ProductEmbeddingStoreError):
    pass
