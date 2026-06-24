from __future__ import annotations

from secrets import compare_digest

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from src.features.product.application.product_embedding_use_case import (
    ProductEmbeddingNotFoundError,
    ProductEmbeddingUseCase,
)
from src.features.product.infrastructure.input.http.model.product_embedding_response import (
    ProductEmbeddingResponse,
)
from src.features.product.infrastructure.output.http.errors import (
    EmbeddingConfigurationError,
    ProductEmbeddingEntryNotFoundError,
    ProductEmbeddingStoreError,
)


def build_product_embedding_router(
    *,
    internal_api_token: str | None,
    use_case: ProductEmbeddingUseCase,
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
        try:
            result = use_case.handle(article_id, force=force)
        except (
            ProductEmbeddingNotFoundError,
            ProductEmbeddingEntryNotFoundError,
        ):
            raise HTTPException(status_code=404, detail="Product not found.") from None
        except ProductEmbeddingStoreError as exc:
            raise HTTPException(
                status_code=503,
                detail="Product embedding maintenance is unavailable.",
            ) from exc
        except EmbeddingConfigurationError as exc:
            raise HTTPException(
                status_code=503,
                detail="Embedding generation is unavailable.",
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail="Embedding provider request failed.",
            ) from exc

        return ProductEmbeddingResponse.model_validate(result, from_attributes=True)

    return router
