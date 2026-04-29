from datetime import datetime

from pydantic import BaseModel, Field


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    is_public: bool = False
    system_prompt: str = '你是一个专业的知识库问答助手。'


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    is_public: bool | None = None
    system_prompt: str | None = None


class KnowledgeBaseResponse(BaseModel):
    id: int
    owner_id: int
    name: str
    description: str | None
    is_public: bool
    system_prompt: str
    created_at: datetime
