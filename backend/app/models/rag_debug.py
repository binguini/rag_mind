from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RAGDebugLog(Base):
    __tablename__ = 'rag_debug_logs'

    id: Mapped[int] = mapped_column(primary_key=True)
    knowledge_base_id: Mapped[int] = mapped_column(ForeignKey('knowledge_bases.id'), index=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey('chat_sessions.id'), nullable=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    question: Mapped[str] = mapped_column(Text)
    rewritten_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    retrieval_params_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    retrieved_hits_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    rerank_before_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    rerank_after_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_context_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    citations_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    generation_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rewrite_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retrieval_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rerank_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prompt_build_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_bad_case: Mapped[bool] = mapped_column(Boolean, default=False)
    bad_case_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bad_case_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
