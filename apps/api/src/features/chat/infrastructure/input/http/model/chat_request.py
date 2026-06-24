from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    model_config = ConfigDict(strict=True)

    site_id: int = Field(..., ge=1)
    query: str = Field(..., min_length=1, max_length=500)
