from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DocumentOperationType(str, Enum):
    retry_requested = 'retry_requested'
    retry_succeeded = 'retry_succeeded'
    retry_failed = 'retry_failed'
    delete_requested = 'delete_requested'
    delete_succeeded = 'delete_succeeded'
    delete_failed = 'delete_failed'
    process_started = 'process_started'
    process_completed = 'process_completed'
    process_failed = 'process_failed'
    parse_started = 'parse_started'
    parse_completed = 'parse_completed'
    chunking_started = 'chunking_started'
    chunking_completed = 'chunking_completed'
    embedding_started = 'embedding_started'
    embedding_completed = 'embedding_completed'
    vector_store_started = 'vector_store_started'
    vector_store_completed = 'vector_store_completed'


class DocumentOperationLog(Base):
    __tablename__ = 'document_operation_logs'

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey('documents.id'), index=True)
    knowledge_base_id: Mapped[int] = mapped_column(ForeignKey('knowledge_bases.id'), index=True)
    operator_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True, index=True)
    operation_type: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(20), default='success', index=True)
    task_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    stage: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    elapsed_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
