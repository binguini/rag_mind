import hashlib
from datetime import datetime
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import Document, DocumentStatus
from app.models.document_chunk import DocumentChunk
from app.models.document_operation_log import DocumentOperationLog, DocumentOperationType
from app.models.kb_member import MemberRole
from app.services.kb_service import KnowledgeBaseService
from app.services.vector_store_service import VectorStoreService

ALLOWED_EXTENSIONS = {'.txt', '.pdf', '.md'}
PREVIEW_MAX_LENGTH = 1200


class DocumentService:
    # 文档服务：负责上传校验、文件落盘、文档状态流转、操作日志和清理回收。
    @staticmethod
    def ensure_permission(db: Session, kb_id: int, user_id: int) -> None:
        # 校验当前用户是否拥有该知识库的上传权限。
        member = KnowledgeBaseService.get_member(db, kb_id, user_id)
        if not member or member.role not in {MemberRole.owner, MemberRole.admin, MemberRole.editor}:
            raise ValueError('无上传权限')

    @staticmethod
    def ensure_read_permission(db: Session, kb_id: int, user_id: int) -> None:
        member = KnowledgeBaseService.get_member(db, kb_id, user_id)
        if not member:
            raise ValueError('无权限访问该知识库')

    @staticmethod
    def compute_md5(content: bytes) -> str:
        return hashlib.md5(content).hexdigest()

    @staticmethod
    def save_file(file: UploadFile, content: bytes, file_md5: str) -> tuple[str, str]:
        # 根据文件内容生成去重后的落盘路径，只允许白名单扩展名。
        settings = get_settings()
        ext = Path(file.filename or '').suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError('仅支持 txt/pdf/md 文件')

        save_dir = Path(settings.upload_dir)
        save_dir.mkdir(parents=True, exist_ok=True)

        save_name = f'{file_md5}{ext}'
        save_path = save_dir / save_name

        if not save_path.exists():
            save_path.write_bytes(content)

        return str(save_path).replace('\\', '/'), ext.replace('.', '')

    @staticmethod
    def build_preview(text: str | None) -> str | None:
        if not text:
            return None
        normalized = text.strip()
        if not normalized:
            return None
        if len(normalized) <= PREVIEW_MAX_LENGTH:
            return normalized
        return f'{normalized[:PREVIEW_MAX_LENGTH].rstrip()}...'

    @staticmethod
    def find_duplicate(db: Session, kb_id: int, file_md5: str) -> Document | None:
        stmt = select(Document).where(
            Document.knowledge_base_id == kb_id,
            Document.file_md5 == file_md5,
            Document.status != DocumentStatus.deleted.value,
        )
        return db.scalar(stmt)

    @staticmethod
    def create_document(
        db: Session,
        kb_id: int,
        uploader_id: int,
        filename: str,
        file_type: str,
        file_md5: str,
        file_path: str,
    ) -> Document:
        doc = Document(
            knowledge_base_id=kb_id,
            uploader_id=uploader_id,
            filename=filename,
            file_type=file_type,
            file_md5=file_md5,
            file_path=file_path,
            status=DocumentStatus.pending.value,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return doc

    @staticmethod
    def set_status(
        db: Session,
        document_id: int,
        status: DocumentStatus,
        error_message: str | None = None,
        chunk_count: int | None = None,
        page_count: int | None = None,
        extracted_preview: str | None = None,
        processing_started_at: datetime | None = None,
        processing_finished_at: datetime | None = None,
        retry_count: int | None = None,
    ) -> Document:
        doc = db.scalar(select(Document).where(Document.id == document_id))
        if not doc:
            raise ValueError('文档不存在')

        doc.status = status.value
        if error_message is not None:
            doc.error_message = error_message
        if chunk_count is not None:
            doc.chunk_count = chunk_count
        if page_count is not None:
            doc.page_count = page_count
        if extracted_preview is not None:
            doc.extracted_preview = extracted_preview
        if processing_started_at is not None:
            doc.processing_started_at = processing_started_at
        if processing_finished_at is not None:
            doc.processing_finished_at = processing_finished_at
        if retry_count is not None:
            doc.retry_count = retry_count
        db.commit()
        db.refresh(doc)
        return doc

    @staticmethod
    def bind_task_id(db: Session, document_id: int, task_id: str) -> Document:
        doc = db.scalar(select(Document).where(Document.id == document_id))
        if not doc:
            raise ValueError('文档不存在')

        doc.task_id = task_id
        db.commit()
        db.refresh(doc)
        return doc

    @staticmethod
    def bind_delete_task_id(db: Session, document_id: int, task_id: str) -> Document:
        doc = db.scalar(select(Document).where(Document.id == document_id))
        if not doc:
            raise ValueError('文档不存在')

        doc.delete_task_id = task_id
        db.commit()
        db.refresh(doc)
        return doc

    @staticmethod
    def list_documents(db: Session, kb_id: int) -> list[Document]:
        stmt = (
            select(Document)
            .where(Document.knowledge_base_id == kb_id, Document.status != DocumentStatus.deleted.value)
            .order_by(Document.id.desc())
        )
        return list(db.scalars(stmt).all())

    @staticmethod
    def get_document(db: Session, document_id: int) -> Document | None:
        return db.scalar(select(Document).where(Document.id == document_id))

    @staticmethod
    def list_document_chunks(db: Session, document_id: int, limit: int = 20) -> list[DocumentChunk]:
        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.asc())
            .limit(limit)
        )
        return list(db.scalars(stmt).all())

    @staticmethod
    def list_operation_logs(db: Session, document_id: int, limit: int = 50) -> list[DocumentOperationLog]:
        stmt = (
            select(DocumentOperationLog)
            .where(DocumentOperationLog.document_id == document_id)
            .order_by(DocumentOperationLog.id.desc())
            .limit(limit)
        )
        return list(db.scalars(stmt).all())

    @staticmethod
    def create_operation_log(
        db: Session,
        document_id: int,
        knowledge_base_id: int,
        operation_type: DocumentOperationType,
        status: str,
        operator_user_id: int | None = None,
        task_id: str | None = None,
        stage: str | None = None,
        elapsed_ms: int | None = None,
        message: str | None = None,
    ) -> DocumentOperationLog:
        # 记录文档处理过程中的关键操作，便于后台排查和审计。
        log = DocumentOperationLog(
            document_id=document_id,
            knowledge_base_id=knowledge_base_id,
            operator_user_id=operator_user_id,
            operation_type=operation_type.value,
            status=status,
            task_id=task_id,
            stage=stage,
            elapsed_ms=elapsed_ms,
            message=message,
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log

    @staticmethod
    def get_processing_duration_ms(doc: Document) -> int | None:
        if not doc.processing_started_at or not doc.processing_finished_at:
            return None
        duration = doc.processing_finished_at - doc.processing_started_at
        return max(int(duration.total_seconds() * 1000), 0)

    @staticmethod
    def cancel_document(db: Session, document_id: int) -> Document:
        doc = db.scalar(select(Document).where(Document.id == document_id))
        if not doc:
            raise ValueError('文档不存在')
        if doc.status in {DocumentStatus.completed.value, DocumentStatus.failed.value, DocumentStatus.deleted.value}:
            return doc
        doc.status = DocumentStatus.failed.value
        doc.error_message = '用户取消任务'
        doc.processing_finished_at = datetime.utcnow()
        db.commit()
        db.refresh(doc)
        return doc

    @staticmethod
    def cleanup_document_artifacts(db: Session, doc: Document, delete_source_file: bool = False) -> None:
        db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc.id))
        db.commit()
        VectorStoreService.delete_document_chunks(doc.id)

        if delete_source_file and doc.file_path:
            file_path = Path(doc.file_path)
            if file_path.exists():
                file_path.unlink()

    @staticmethod
    def retry_document(db: Session, document_id: int, operator_user_id: int | None = None) -> Document:
        # 将失败文档恢复到待处理状态，并清理旧的切片与向量数据。
        doc = db.scalar(select(Document).where(Document.id == document_id))
        if not doc:
            raise ValueError('文档不存在')
        if doc.status not in {DocumentStatus.failed.value}:
            raise ValueError('仅失败文档支持重试')

        DocumentService.create_operation_log(
            db,
            document_id=doc.id,
            knowledge_base_id=doc.knowledge_base_id,
            operation_type=DocumentOperationType.retry_requested,
            status='accepted',
            operator_user_id=operator_user_id,
            message='用户发起文档重试',
        )
        DocumentService.cleanup_document_artifacts(db, doc, delete_source_file=False)
        doc.status = DocumentStatus.pending.value
        doc.error_message = None
        doc.chunk_count = 0
        doc.page_count = 0
        doc.extracted_preview = None
        doc.processing_started_at = None
        doc.processing_finished_at = None
        doc.retry_count = (doc.retry_count or 0) + 1
        doc.task_id = None
        db.commit()
        db.refresh(doc)
        return doc

    @staticmethod
    def mark_delete_requested(
        db: Session,
        document_id: int,
        delete_source_file: bool = False,
        operator_user_id: int | None = None,
    ) -> Document:
        doc = db.scalar(select(Document).where(Document.id == document_id))
        if not doc:
            raise ValueError('文档不存在')
        if doc.status == DocumentStatus.running.value:
            raise ValueError('文档处理中，暂不支持删除')
        if doc.status == DocumentStatus.deleted.value:
            return doc
        if doc.status == DocumentStatus.deleting.value:
            return doc

        doc.status = DocumentStatus.deleting.value
        doc.delete_source_file_requested = delete_source_file
        doc.delete_task_id = None
        doc.error_message = None
        db.commit()
        db.refresh(doc)
        DocumentService.create_operation_log(
            db,
            document_id=doc.id,
            knowledge_base_id=doc.knowledge_base_id,
            operation_type=DocumentOperationType.delete_requested,
            status='accepted',
            operator_user_id=operator_user_id,
            stage='delete',
            message='用户发起文档删除',
        )
        return doc

    @staticmethod
    def finalize_delete(db: Session, document_id: int) -> Document:
        # 真正执行删除后的收尾工作：清理切片、向量和源文件，并更新状态。
        doc = db.scalar(select(Document).where(Document.id == document_id))
        if not doc:
            raise ValueError('文档不存在')

        DocumentService.cleanup_document_artifacts(db, doc, delete_source_file=doc.delete_source_file_requested)
        doc.status = DocumentStatus.deleted.value
        doc.processing_finished_at = datetime.utcnow()
        db.commit()
        db.refresh(doc)
        return doc

    @staticmethod
    def mark_delete_failed(db: Session, document_id: int, error_message: str) -> Document:
        doc = db.scalar(select(Document).where(Document.id == document_id))
        if not doc:
            raise ValueError('文档不存在')
        doc.status = DocumentStatus.delete_failed.value
        doc.error_message = error_message
        doc.processing_finished_at = datetime.utcnow()
        db.commit()
        db.refresh(doc)
        return doc
