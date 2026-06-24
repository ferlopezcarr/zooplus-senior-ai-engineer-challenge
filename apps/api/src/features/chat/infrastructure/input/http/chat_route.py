from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.features.chat.application.chat_use_case import ChatUseCase
from src.features.chat.infrastructure.input.http.chat_mapper import (
    to_chat,
    to_chat_response,
)
from src.features.chat.infrastructure.input.http.model.chat_request import ChatRequest
from src.features.chat.infrastructure.input.http.model.chat_response import ChatResponse
from src.features.chat.infrastructure.output.http.errors import (
    CatalogDatabaseUnavailableError,
)


def build_chat_router(use_case: ChatUseCase) -> APIRouter:
    router = APIRouter(prefix="/public")

    @router.post("/chat", response_model=ChatResponse)
    def chat_endpoint(body: ChatRequest) -> ChatResponse:
        try:
            chat = to_chat(body)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        try:
            return to_chat_response(use_case.handle(chat))
        except CatalogDatabaseUnavailableError as exc:
            raise HTTPException(
                status_code=503,
                detail="Catalog retrieval is unavailable.",
            ) from exc

    return router
