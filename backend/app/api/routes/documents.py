from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id, get_db_session
from app.models.document import DocumentStatus
from app.schemas.document import (
    DocumentChunkPreview,
    DocumentDetailResponse,
    DocumentOperationLogResponse,
    DocumentUploadResponse,
)
from app.services.document_service import DocumentService
from app.tasks.document_tasks import delete_document_task, process_document_task

router = APIRouter(prefix='/documents', tags=['documents'])
# 文档接口：包含上传、查询、重试、取消、删除以及切片/操作日志查看。


def serialize_document(doc) -> DocumentDetailResponse:
    # 将数据库中的文档 ORM 对象转换为前端需要的响应结构。
    return DocumentDetailResponse(
        id=doc.id,
        knowledge_base_id=doc.knowledge_base_id,
        filename=doc.filename,
        file_type=doc.file_type,
        file_md5=doc.file_md5,
        status=DocumentStatus(doc.status),
        task_id=doc.task_id,
        created_at=doc.created_at,
        chunk_count=doc.chunk_count,
        error_message=doc.error_message,
        page_count=doc.page_count,
        extracted_preview=doc.extracted_preview,
        processing_started_at=doc.processing_started_at,
        processing_finished_at=doc.processing_finished_at,
        retry_count=doc.retry_count,
        processing_duration_ms=DocumentService.get_processing_duration_ms(doc),
        delete_task_id=doc.delete_task_id,
    )


@router.post('/upload', response_model=DocumentUploadResponse)
async def upload_document(
    # 上传文档：校验权限、做去重、落盘并异步触发解析任务。
    kb_id: int = Form(...),
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
):
    try:
        DocumentService.ensure_permission(db, kb_id, user_id)

        content = await file.read()
        if not content:
            raise ValueError('文件为空')

        file_md5 = DocumentService.compute_md5(content)
        duplicate = DocumentService.find_duplicate(db, kb_id, file_md5)

        if duplicate and duplicate.status in {
            DocumentStatus.pending.value,
            DocumentStatus.running.value,
            DocumentStatus.completed.value,
        }:
            return DocumentUploadResponse(
                id=duplicate.id,
                knowledge_base_id=duplicate.knowledge_base_id,
                filename=duplicate.filename,
                file_type=duplicate.file_type,
                file_md5=duplicate.file_md5,
                status=DocumentStatus(duplicate.status),
                task_id=duplicate.task_id,
                created_at=duplicate.created_at,
            )

        file_path, file_type = DocumentService.save_file(file, content, file_md5)
        document = DocumentService.create_document(
            db=db,
            kb_id=kb_id,
            uploader_id=user_id,
            filename=file.filename or f'file.{file_type}',
            file_type=file_type,
            file_md5=file_md5,
            file_path=file_path,
        )

        task = process_document_task.delay(document.id)
        document = DocumentService.bind_task_id(db, document.id, task.id)

        return DocumentUploadResponse(
            id=document.id,
            knowledge_base_id=document.knowledge_base_id,
            filename=document.filename,
            file_type=document.file_type,
            file_md5=document.file_md5,
            status=DocumentStatus(document.status),
            task_id=document.task_id,
            created_at=document.created_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get('', response_model=list[DocumentDetailResponse])
def list_documents(
    # 列出当前知识库下可见的文档列表。
    kb_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
):
    try:
        DocumentService.ensure_read_permission(db, kb_id, user_id)
        docs = DocumentService.list_documents(db, kb_id)
        return [serialize_document(d) for d in docs]
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get('/{document_id}', response_model=DocumentDetailResponse)
def get_document(
    # 查看单个文档详情。
    document_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
):
    doc = DocumentService.get_document(db, document_id)
    if not doc or doc.status == DocumentStatus.deleted.value:
        raise HTTPException(status_code=404, detail='文档不存在')
    try:
        DocumentService.ensure_read_permission(db, doc.knowledge_base_id, user_id)
        return serialize_document(doc)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get('/{document_id}/chunks', response_model=list[DocumentChunkPreview])
def list_document_chunks(
    # 查看文档切片预览，便于排查切分结果是否符合预期。
    document_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
):
    doc = DocumentService.get_document(db, document_id)
    if not doc or doc.status == DocumentStatus.deleted.value:
        raise HTTPException(status_code=404, detail='文档不存在')
    try:
        DocumentService.ensure_read_permission(db, doc.knowledge_base_id, user_id)
        chunks = DocumentService.list_document_chunks(db, document_id, limit=limit)
        return [
            DocumentChunkPreview(
                id=chunk.id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                source_page=chunk.source_page,
                source_file=chunk.source_file,
                created_at=chunk.created_at,
            )
            for chunk in chunks
        ]
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get('/{document_id}/logs', response_model=list[DocumentOperationLogResponse])
def list_document_logs(
    # 查看文档处理过程中的操作日志。
    document_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
):
    doc = DocumentService.get_document(db, document_id)
    if not doc or doc.status == DocumentStatus.deleted.value:
        raise HTTPException(status_code=404, detail='文档不存在')
    try:
        DocumentService.ensure_read_permission(db, doc.knowledge_base_id, user_id)
        logs = DocumentService.list_operation_logs(db, document_id, limit=limit)
        return [
            DocumentOperationLogResponse(
                id=log.id,
                operation_type=log.operation_type,
                status=log.status,
                task_id=log.task_id,
                stage=log.stage,
                elapsed_ms=log.elapsed_ms,
                message=log.message,
                created_at=log.created_at,
            )
            for log in logs
        ]
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post('/{document_id}/cancel', response_model=DocumentDetailResponse)
def cancel_document(
    # 取消尚未结束的文档处理任务。
    document_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
):
    doc = DocumentService.get_document(db, document_id)
    if not doc or doc.status == DocumentStatus.deleted.value:
        raise HTTPException(status_code=404, detail='文档不存在')
    try:
        DocumentService.ensure_permission(db, doc.knowledge_base_id, user_id)
        doc = DocumentService.cancel_document(db, document_id)
        return serialize_document(doc)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/{document_id}/retry', response_model=DocumentDetailResponse)
def retry_document(
    # 对失败文档重新入队处理。
    document_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
):
    doc = DocumentService.get_document(db, document_id)
    if not doc or doc.status == DocumentStatus.deleted.value:
        raise HTTPException(status_code=404, detail='文档不存在')
    try:
        DocumentService.ensure_permission(db, doc.knowledge_base_id, user_id)
        doc = DocumentService.retry_document(db, document_id, operator_user_id=user_id)
        task = process_document_task.delay(doc.id)
        doc = DocumentService.bind_task_id(db, doc.id, task.id)
        return serialize_document(doc)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete('/{document_id}', response_model=DocumentDetailResponse)
def delete_document(
    # 申请删除文档，并在后台异步执行清理任务。
    document_id: int,
    delete_source_file: bool = Query(default=False),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
):
    doc = DocumentService.get_document(db, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail='文档不存在')
    try:
        DocumentService.ensure_permission(db, doc.knowledge_base_id, user_id)
        doc = DocumentService.mark_delete_requested(
            db,
            document_id,
            delete_source_file=delete_source_file,
            operator_user_id=user_id,
        )
        if doc.status == DocumentStatus.deleting.value and not doc.delete_task_id:
            task = delete_document_task.delay(doc.id)
            doc = DocumentService.bind_delete_task_id(db, doc.id, task.id)
        return serialize_document(doc)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
