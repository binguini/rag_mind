from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ChatMode(str, Enum):
    GENERAL = 'general'
    RAG = 'rag'


class ChatSessionStatus(str, Enum):
    ACTIVE = 'active'
    ARCHIVED = 'archived'
    DELETED = 'deleted'


class ChatSession(Base):
    __tablename__ = 'chat_sessions'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    mode: Mapped[str] = mapped_column(String(20), index=True)
    knowledge_base_id: Mapped[int | None] = mapped_column(ForeignKey('knowledge_bases.id'), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200), default='新对话')
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=ChatSessionStatus.ACTIVE.value, index=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    last_message_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
