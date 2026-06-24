from pydantic import BaseModel, ConfigDict, Field

from src.features.chat.domain.model import MAX_QUERY_LENGTH


class ChatRequest(BaseModel):
    model_config = ConfigDict(strict=True)

    site_id: int = Field(..., ge=1)
    query: str = Field(..., min_length=1, max_length=MAX_QUERY_LENGTH)
