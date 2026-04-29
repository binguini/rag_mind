from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RetrievalConfigPayload(BaseModel):
    top_k: int = Field(default=8, ge=1, le=50)
    threshold: float = Field(default=0.2, ge=0.0, le=1.0)
    rerank_enabled: bool = True
    chunk_size: int = Field(default=800, ge=100, le=4000)
    chunk_overlap: int = Field(default=100, ge=0, le=2000)
    scope: str = Field(default='knowledge_base', pattern='^(knowledge_base|session)$')


class RetrievalConfigResponse(BaseModel):
    scope: str
    knowledge_base_id: int | None = None
    session_id: int | None = None
    top_k: int
    threshold: float
    rerank_enabled: bool
    chunk_size: int
    chunk_overlap: int
    updated_at: datetime | None = None


class RAGDebugLogItem(BaseModel):
    id: int
    knowledge_base_id: int
    session_id: int | None = None
    user_id: int
    question: str
    rewritten_question: str | None = None
    answer: str | None = None
    retrieval_params: dict[str, Any] | None = None
    retrieved_hits: list[dict[str, Any]] = []
    rerank_before: list[dict[str, Any]] = []
    rerank_after: list[dict[str, Any]] = []
    prompt_context: list[dict[str, Any]] = []
    prompt_text: str | None = None
    citations: list[dict[str, Any]] = []
    generation_stage: str | None = None
    error_message: str | None = None
    total_duration_ms: int | None = None
    rewrite_duration_ms: int | None = None
    embedding_duration_ms: int | None = None
    retrieval_duration_ms: int | None = None
    rerank_duration_ms: int | None = None
    prompt_build_duration_ms: int | None = None
    is_bad_case: bool = False
    bad_case_category: str | None = None
    bad_case_note: str | None = None
    created_at: datetime


class RAGDebugLogListResponse(BaseModel):
    items: list[RAGDebugLogItem]
    total: int
    limit: int
    offset: int


class RAGDebugLogMarkBadCasePayload(BaseModel):
    is_bad_case: bool
    bad_case_category: str | None = Field(default=None, max_length=50)
    bad_case_note: str | None = Field(default=None, max_length=2000)
