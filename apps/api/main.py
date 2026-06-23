"""FastAPI bootstrap for the assistant API."""

import math
import logging
from collections.abc import Mapping
from os import getenv
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import FastAPI
from src.application.answer_generator import (
    AnswerGenerator,
    DeterministicAnswerGenerator,
    LlmAnswerGenerator,
)
from src.application.use_case.chat_use_case import ChatUseCase
from src.infrastructure.input.http.chat.chat_route import build_chat_router
from src.infrastructure.input.http.products.product_embedding_route import (
    build_product_embedding_router,
)
from src.infrastructure.output.embedding_client import (
    DEFAULT_EMBEDDING_TIMEOUT_SECONDS,
    EmbeddingConfigurationError,
    OpenAICompatibleEmbeddingClient,
    build_embeddings_url,
)
from src.infrastructure.output.llm_answer_client import (
    DEFAULT_LLM_TIMEOUT_SECONDS,
    OpenAICompatibleAnswerClient,
    build_llm_chat_completions_url,
)
from src.infrastructure.output.product_embedding_store import (
    DatabaseProductEmbeddingStore,
)
from src.infrastructure.output.product_database_retriever import (
    PRODUCT_CATALOG_DATABASE_URL_ENV,
    DatabaseProductRetriever,
)

DOTENV_PATH = Path(__file__).resolve().parent / ".env"

LOGGER = logging.getLogger(__name__)

_missing_llm_config_warnings_emitted: set[str] = set()


def build_app() -> FastAPI:
    """Build the FastAPI app for the current repository runtime."""

    load_dotenv(DOTENV_PATH)

    app = FastAPI(
        title="Zooplus Assistant API",
        version="0.1.0",
        description="FastAPI service exposing operational health, public grounded catalog chat, and internal product embedding maintenance endpoints.",
    )

    database_url = _get_required_database_url()
    retriever = _build_product_retriever(database_url)

    @app.get("/")
    async def root() -> Mapping[str, str]:
        """Liveness ping for the API shell."""

        return {"status": "ok", "service": "zooplus-assistant-api"}

    @app.get("/health")
    async def health() -> Mapping[str, str]:
        """Health probe used by local and CI checks."""

        return {"status": "healthy"}

    use_case = ChatUseCase(retriever, answer_generator=_build_answer_generator())
    app.include_router(build_chat_router(use_case))
    app.include_router(
        build_product_embedding_router(
            database_url=database_url,
            internal_api_token=_get_non_blank_env("INTERNAL_API_TOKEN"),
            embedding_client_factory=_build_embedding_client,
            embedding_store_factory=DatabaseProductEmbeddingStore,
        )
    )

    return app


def _build_answer_generator() -> AnswerGenerator:
    base_url = _get_non_blank_env("LLM_BASE_URL")
    if not base_url:
        _warn_missing_llm_config_once("LLM_BASE_URL")
        return DeterministicAnswerGenerator()

    build_llm_chat_completions_url(base_url)

    api_key = _get_non_blank_env("LLM_API_KEY")
    if not api_key:
        _warn_missing_llm_config_once("LLM_API_KEY")
        return DeterministicAnswerGenerator()

    timeout_seconds = _get_llm_timeout_seconds()
    model = getenv("LLM_MODEL", "gpt-4o-mini")
    LOGGER.info(
        "LLM answer generation enabled with model=%s base_url=%s.",
        model,
        _safe_log_url(base_url),
    )
    client = OpenAICompatibleAnswerClient(
        api_key=api_key,
        model=model,
        base_url=base_url,
        timeout_seconds=timeout_seconds,
    )
    return LlmAnswerGenerator(client)


def _get_required_database_url() -> str:
    database_url = _get_non_blank_env(PRODUCT_CATALOG_DATABASE_URL_ENV)
    if not database_url:
        raise ValueError(
            f"{PRODUCT_CATALOG_DATABASE_URL_ENV} must be set to a non-blank PostgreSQL connection string for runtime product retrieval."
        )

    return database_url


def _build_product_retriever(database_url: str) -> DatabaseProductRetriever:

    retriever = DatabaseProductRetriever(database_url)
    readiness_error = retriever.readiness_error()
    if readiness_error:
        LOGGER.warning(
            "Catalog retrieval startup check failed for database_url=%s.",
            _safe_log_url(database_url),
        )
        raise ValueError(
            f"{PRODUCT_CATALOG_DATABASE_URL_ENV} must point to a ready PostgreSQL catalog database."
        )

    LOGGER.info(
        "Catalog retrieval enabled from PostgreSQL database_url=%s.",
        _safe_log_url(database_url),
    )
    return retriever


def _build_embedding_client() -> OpenAICompatibleEmbeddingClient:
    base_url = _get_non_blank_env("EMBEDDING_BASE_URL")
    api_key = _get_non_blank_env("EMBEDDING_API_KEY")
    model = _get_non_blank_env("EMBEDDING_MODEL")

    if not base_url or not api_key or not model:
        raise EmbeddingConfigurationError("Embedding generation is unavailable.")

    try:
        build_embeddings_url(base_url)
        timeout_seconds = _get_timeout_seconds(
            "EMBEDDING_TIMEOUT_SECONDS",
            DEFAULT_EMBEDDING_TIMEOUT_SECONDS,
        )
    except ValueError as exc:
        raise EmbeddingConfigurationError(
            "Embedding generation is unavailable."
        ) from exc

    client = OpenAICompatibleEmbeddingClient(
        api_key=api_key,
        model=model,
        base_url=base_url,
        timeout_seconds=timeout_seconds,
    )
    return client


def _get_non_blank_env(name: str) -> str | None:
    value = getenv(name)
    if value is None:
        return None

    normalized_value = value.strip()
    if not normalized_value:
        return None

    return normalized_value


def _warn_missing_llm_config_once(name: str) -> None:
    if name in _missing_llm_config_warnings_emitted:
        return

    LOGGER.warning(
        "%s is not set after loading %s; using deterministic answer generation.",
        name,
        DOTENV_PATH,
    )
    _missing_llm_config_warnings_emitted.add(name)


def _get_llm_timeout_seconds() -> float:
    return _get_timeout_seconds("LLM_TIMEOUT_SECONDS", DEFAULT_LLM_TIMEOUT_SECONDS)


def _get_timeout_seconds(name: str, default: float) -> float:
    value = getenv(name)
    if value is None or not value.strip():
        return default

    try:
        timeout_seconds = float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive number") from exc

    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError(f"{name} must be a positive number")

    return timeout_seconds


def _safe_log_url(url: str) -> str:
    parsed = urlparse(url.strip())
    return parsed._replace(netloc=parsed.netloc.rsplit("@", 1)[-1]).geturl()
