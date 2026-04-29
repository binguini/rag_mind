from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.chat_message import ChatMessageStatus, ChatRole
from app.models.chat_session import ChatMode, ChatSessionStatus


class ChatSessionCreateRequest(BaseModel):
    # 创建会话时使用的请求体。
    mode: ChatMode
    knowledge_base_id: int | None = Field(default=None, gt=0)
    title: str | None = Field(default=None, max_length=200)


class ChatSessionUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    status: ChatSessionStatus | None = None


class ChatSessionItem(BaseModel):
    # 前端会话列表与详情页使用的会话数据结构。
    id: int
    mode: ChatMode
    knowledge_base_id: int | None = None
    title: str
    summary: str | None = None
    status: ChatSessionStatus
    message_count: int
    last_message_at: datetime
    created_at: datetime
    updated_at: datetime


class ChatMessageItem(BaseModel):
    # 前端消息列表展示所需的完整消息结构。
    id: int
    session_id: int
    role: ChatRole
    content: str
    content_type: str
    status: ChatMessageStatus
    citations: list[dict[str, Any]] = []
    meta: dict[str, Any] | None = None
    error_message: str | None = None
    parent_message_id: int | None = None
    created_at: datetime
    updated_at: datetime


class ChatStreamRequest(BaseModel):
    message: str = Field(min_length=1)


class ChatStreamEvent(BaseModel):
    type: str
    message_id: int | None = None
    content: str | None = None
    answer: str | None = None
    citations: list[dict[str, Any]] | None = None
    error: str | None = None
