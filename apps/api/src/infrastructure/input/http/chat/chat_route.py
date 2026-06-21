from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.application.chat_use_case import ChatUseCase
from src.infrastructure.input.http.chat.service import (
    to_chat,
    to_chat_response,
)
from src.infrastructure.input.http.chat.model import ChatRequest, ChatResponse
from src.infrastructure.output.product_retriever import DatasetNotReadyError


def build_chat_router(use_case: ChatUseCase) -> APIRouter:
    router = APIRouter()

    @router.post("/chat", response_model=ChatResponse)
    async def chat_endpoint(body: ChatRequest) -> ChatResponse:
        try:
            chat = to_chat(body)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        try:
            return to_chat_response(use_case.handle(chat))
        except DatasetNotReadyError as exc:
            raise HTTPException(
                status_code=503,
                detail="Catalog dataset is unavailable.",
            ) from exc

    return router
