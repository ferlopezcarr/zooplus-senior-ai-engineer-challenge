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
from src.infrastructure.output.llm_answer_client import (
    DEFAULT_LLM_TIMEOUT_SECONDS,
    OpenAICompatibleAnswerClient,
    build_llm_chat_completions_url,
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
        description="FastAPI service exposing grounded catalog chat and health endpoints.",
    )

    retriever = _build_product_retriever()

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


def _build_product_retriever() -> DatabaseProductRetriever:
    database_url = _get_non_blank_env(PRODUCT_CATALOG_DATABASE_URL_ENV)
    if not database_url:
        raise ValueError(
            f"{PRODUCT_CATALOG_DATABASE_URL_ENV} must be set to a non-blank PostgreSQL connection string for runtime product retrieval."
        )

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
    value = getenv("LLM_TIMEOUT_SECONDS")
    if value is None or not value.strip():
        return DEFAULT_LLM_TIMEOUT_SECONDS

    try:
        timeout_seconds = float(value)
    except ValueError as exc:
        raise ValueError("LLM_TIMEOUT_SECONDS must be a positive number") from exc

    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("LLM_TIMEOUT_SECONDS must be a positive number")

    return timeout_seconds


def _safe_log_url(url: str) -> str:
    parsed = urlparse(url.strip())
    return parsed._replace(netloc=parsed.netloc.rsplit("@", 1)[-1]).geturl()
