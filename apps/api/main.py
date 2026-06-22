"""FastAPI bootstrap for the assistant API."""

from collections.abc import Mapping
from os import getenv
from pathlib import Path

from fastapi import FastAPI
from src.application.answer_generator import (
    AnswerGenerator,
    DeterministicAnswerGenerator,
    LlmAnswerGenerator,
)
from src.application.chat_use_case import ChatUseCase
from src.infrastructure.input.http.chat.chat_route import build_chat_router
from src.infrastructure.output.llm_answer_client import (
    DEFAULT_LLM_TIMEOUT_SECONDS,
    OpenAICompatibleAnswerClient,
)
from src.infrastructure.output.product_retriever import ProductRetriever


DEFAULT_DATASET_PATH = (
    Path(__file__).resolve().parents[2] / "data/product_catalog_dataset.json"
)


def build_app() -> FastAPI:
    """Build the FastAPI app for the current repository runtime."""

    app = FastAPI(
        title="Zooplus Assistant API",
        version="0.1.0",
        description="FastAPI service exposing grounded catalog chat and health endpoints.",
    )

    dataset_path = Path(getenv("CATALOG_DATASET_PATH", str(DEFAULT_DATASET_PATH)))
    retriever = ProductRetriever(dataset_path)

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
    api_key = getenv("LLM_API_KEY")
    if not api_key:
        return DeterministicAnswerGenerator()

    model = getenv("LLM_MODEL", "gpt-4o-mini")
    base_url = getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    client = OpenAICompatibleAnswerClient(
        api_key=api_key,
        model=model,
        base_url=base_url,
        timeout_seconds=DEFAULT_LLM_TIMEOUT_SECONDS,
    )
    return LlmAnswerGenerator(client)


app = build_app()
