from datetime import datetime

from pydantic import BaseModel

from app.models.document import DocumentStatus


class DocumentUploadResponse(BaseModel):
    id: int
    knowledge_base_id: int
    filename: str
    file_type: str
    file_md5: str
    status: DocumentStatus
    task_id: str | None
    created_at: datetime


class DocumentChunkPreview(BaseModel):
    id: int
    chunk_index: int
    content: str
    source_page: int | None
    source_file: str
    created_at: datetime


class DocumentOperationLogResponse(BaseModel):
    id: int
    operation_type: str
    status: str
    task_id: str | None
    stage: str | None
    elapsed_ms: int | None
    message: str | None
    created_at: datetime


class DocumentDetailResponse(DocumentUploadResponse):
    chunk_count: int
    error_message: str | None
    page_count: int
    extracted_preview: str | None
    processing_started_at: datetime | None
    processing_finished_at: datetime | None
    retry_count: int
    processing_duration_ms: int | None
    delete_task_id: str | None


class DocumentProgressMessage(BaseModel):
    document_id: int
    task_id: str | None = None
    status: DocumentStatus
    progress: int
    message: str


class DocumentListQuery(BaseModel):
    kb_id: int
    status: DocumentStatus | None = None
