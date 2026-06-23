from __future__ import annotations

from collections.abc import Callable
from secrets import compare_digest

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from src.infrastructure.input.http.products.model import ProductEmbeddingResponse
from src.infrastructure.output.embedding_client import (
    EmbeddingConfigurationError,
    EmbeddingProviderHttpError,
)
from src.infrastructure.output.product_embedding_store import (
    ProductEmbeddingEntryNotFoundError,
    DatabaseProductEmbeddingStore,
    ProductEmbeddingStoreError,
)


def build_product_embedding_router(
    *,
    database_url: str,
    internal_api_token: str | None,
    embedding_client_factory: Callable[[], object],
    embedding_store_factory: Callable[[str], DatabaseProductEmbeddingStore],
) -> APIRouter:
    def require_internal_token(
        internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
    ) -> None:
        if internal_api_token is None:
            raise HTTPException(
                status_code=503,
                detail="Product embedding maintenance is unavailable.",
            )

        if internal_token is None:
            raise HTTPException(status_code=401, detail="Not authorized.")

        if not compare_digest(internal_token, internal_api_token):
            raise HTTPException(status_code=403, detail="Not authorized.")

    router = APIRouter(
        prefix="/internal",
        dependencies=[Depends(require_internal_token)],
    )

    @router.post(
        "/products/{article_id}/embedding",
        response_model=ProductEmbeddingResponse,
    )
    def generate_product_embedding(
        article_id: int,
        force: bool = Query(default=False),
    ) -> ProductEmbeddingResponse:
        store = embedding_store_factory(database_url)

        try:
            entry = store.get_entry(article_id)
        except ProductEmbeddingStoreError as exc:
            raise HTTPException(
                status_code=503,
                detail="Product embedding maintenance is unavailable.",
            ) from exc

        if entry is None:
            raise HTTPException(status_code=404, detail="Product not found.")

        if entry.has_embedding and not force:
            return ProductEmbeddingResponse(
                article_id=article_id,
                status="already_embedded",
                model=None,
                dimensions=None,
            )

        try:
            client = embedding_client_factory()
        except EmbeddingConfigurationError as exc:
            raise HTTPException(
                status_code=503,
                detail="Embedding generation is unavailable.",
            ) from exc

        try:
            embedding = client.embed(entry.embedding_document)
            store.save_embedding(article_id, embedding)
        except ProductEmbeddingEntryNotFoundError:
            raise HTTPException(status_code=404, detail="Product not found.") from None
        except EmbeddingProviderHttpError as exc:
            raise HTTPException(
                status_code=502,
                detail="Embedding provider request failed.",
            ) from exc
        except ProductEmbeddingStoreError as exc:
            raise HTTPException(
                status_code=503,
                detail="Product embedding maintenance is unavailable.",
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail="Embedding provider request failed.",
            ) from exc

        return ProductEmbeddingResponse(
            article_id=article_id,
            status="recalculated" if entry.has_embedding else "embedded",
            model=getattr(client, "model", None),
            dimensions=len(embedding),
        )

    return router
