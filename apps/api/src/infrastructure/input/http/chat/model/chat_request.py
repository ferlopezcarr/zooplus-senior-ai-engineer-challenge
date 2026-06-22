from pydantic import BaseModel, Field, field_validator

from src.domain.model.query import MAX_QUERY_LENGTH


class ChatRequest(BaseModel):
    site_id: int = Field(strict=True, gt=0)
    query: str = Field(max_length=MAX_QUERY_LENGTH)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be blank")
        return value
