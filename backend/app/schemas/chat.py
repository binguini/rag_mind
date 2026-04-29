from pydantic import BaseModel, Field


class GenericChatRequest(BaseModel):
    message: str = Field(min_length=1)
    history: list[dict] = []


class GenericChatResponse(BaseModel):
    answer: str
