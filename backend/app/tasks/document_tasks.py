import logging
from datetime import datetime
from pathlib import Path
from time import perf_counter

from pypdf import PdfReader
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.celery_app import celery_app
from app.models.document import Document, DocumentStatus
from app.models.document_operation_log import DocumentOperationType
from app.services.document_index_service import DocumentIndexService
from app.services.document_service import DocumentService
from app.services.progress_service import publish_progress

logger = logging.getLogger(__name__)


def _count_text_chunks(text: str, chunk_size: int = 500) -> int:
    if not text.strip():
        return 0
    return max(1, (len(text) + chunk_size - 1) // chunk_size)


def _publish(task_id: str, document_id: int, status: DocumentStatus, progress: int, message: str) -> None:
    logger.info(
        'document task progress task_id=%s document_id=%s status=%s progress=%s message=%s',
        task_id,
        document_id,
        status.value,
        progress,
        message,
    )
    publish_progress(task_id, document_id, status, progress, message)


def _log_step(step_name: str, started_at: float, **extra: object) -> int:
    elapsed_ms = round((perf_counter() - started_at) * 1000)
    logger.info('document task step=%s elapsed_ms=%s extra=%s', step_name, elapsed_ms, extra)
    return elapsed_ms


@celery_app.task(name='app.tasks.document_tasks.process_document_task', bind=True)
def process_document_task(self, document_id: int):
    settings = get_settings()
    engine = create_engine(settings.db_url, future=True)

    logger.info('document task started document_id=%s db_url=%s', document_id, settings.db_url)
    task_started_at = perf_counter()

    with Session(engine) as db:
        doc = db.scalar(select(Document).where(Document.id == document_id))
        if not doc:
            logger.warning('document task aborted because document not found document_id=%s', document_id)
            return

        task_id = self.request.id
        doc.task_id = task_id
        doc.status = DocumentStatus.running.value
        doc.processing_started_at = datetime.utcnow()
        doc.processing_finished_at = None
        db.commit()
        db.refresh(doc)
        DocumentService.create_operation_log(
            db,
            document_id=doc.id,
            knowledge_base_id=doc.knowledge_base_id,
            operation_type=DocumentOperationType.process_started,
            status='running',
            task_id=task_id,
            stage='processing',
            message='文档处理任务开始',
        )
        logger.info(
            'document task state updated to running task_id=%s document_id=%s file=%s type=%s path=%s',
            task_id,
            doc.id,
            doc.filename,
            doc.file_type,
            doc.file_path,
        )

        _publish(task_id, doc.id, DocumentStatus.running, 5, '任务已接收，开始处理')

        try:
            parse_started_at = perf_counter()
            page_count = 0
            DocumentService.create_operation_log(
                db,
                document_id=doc.id,
                knowledge_base_id=doc.knowledge_base_id,
                operation_type=DocumentOperationType.parse_started,
                status='running',
                task_id=task_id,
                stage='parsing',
                message='开始解析文档',
            )
            if doc.file_type in {'txt', 'md'}:
                label = 'Markdown 文档' if doc.file_type == 'md' else 'TXT 文本'
                _publish(task_id, doc.id, DocumentStatus.running, 15, f'正在解析{label}')
                text = Path(doc.file_path).read_text(encoding='utf-8', errors='ignore')
                page_count = 1 if text.strip() else 0
                logger.info('%s parsed document_id=%s chars=%s', doc.file_type, doc.id, len(text))
            elif doc.file_type == 'pdf':
                _publish(task_id, doc.id, DocumentStatus.running, 15, '正在解析 PDF 文档')
                reader = PdfReader(doc.file_path)
                page_count = len(reader.pages)
                logger.info('pdf loaded document_id=%s pages=%s', doc.id, page_count)
                text = '\n'.join(page.extract_text() or '' for page in reader.pages)
                logger.info('pdf text extracted document_id=%s chars=%s', doc.id, len(text))
            else:
                raise ValueError('不支持的文件类型')
            parse_elapsed_ms = _log_step('parse_document', parse_started_at, document_id=doc.id, file_type=doc.file_type, text_length=len(text))
            DocumentService.create_operation_log(
                db,
                document_id=doc.id,
                knowledge_base_id=doc.knowledge_base_id,
                operation_type=DocumentOperationType.parse_completed,
                status='success',
                task_id=task_id,
                stage='parsing',
                elapsed_ms=parse_elapsed_ms,
                message=f'文档解析完成，提取文本长度 {len(text)}',
            )

            chunk_estimate_started_at = perf_counter()
            _publish(task_id, doc.id, DocumentStatus.running, 35, '文档解析完成，正在切分段落')
            chunk_count = _count_text_chunks(text) if doc.file_type in {'txt', 'md'} else (max(1, page_count or 0) if text.strip() else (page_count or 0))
            _log_step('estimate_chunks', chunk_estimate_started_at, document_id=doc.id, chunk_count=chunk_count)

            _publish(task_id, doc.id, DocumentStatus.running, 55, '切分完成，准备生成向量')
            chunk_count = max(1, chunk_count)
            doc.chunk_count = chunk_count
            doc.page_count = page_count
            doc.extracted_preview = DocumentService.build_preview(text)
            db.commit()
            logger.info('chunk count estimated document_id=%s chunk_count=%s', doc.id, chunk_count)

            _publish(task_id, doc.id, DocumentStatus.running, 75, '正在生成向量并写入 Milvus')
            indexed_chunks = DocumentIndexService.index_document(db, doc)
            doc.chunk_count = indexed_chunks or chunk_count
            db.commit()
            logger.info(
                'document indexed document_id=%s indexed_chunks=%s final_chunk_count=%s',
                doc.id,
                indexed_chunks,
                doc.chunk_count,
            )

            _publish(task_id, doc.id, DocumentStatus.running, 95, '向量入库完成，准备标记完成')
            doc.status = DocumentStatus.completed.value
            doc.error_message = None
            doc.processing_finished_at = datetime.utcnow()
            db.commit()
            total_elapsed_ms = _log_step('process_document_task_total', task_started_at, document_id=doc.id, task_id=task_id, status='completed')
            DocumentService.create_operation_log(
                db,
                document_id=doc.id,
                knowledge_base_id=doc.knowledge_base_id,
                operation_type=DocumentOperationType.process_completed,
                status='success',
                task_id=task_id,
                stage='processing',
                elapsed_ms=total_elapsed_ms,
                message='文档处理完成',
            )
            logger.info('document task completed document_id=%s task_id=%s chunk_count=%s', doc.id, task_id, doc.chunk_count)
            if doc.retry_count > 0:
                DocumentService.create_operation_log(
                    db,
                    document_id=doc.id,
                    knowledge_base_id=doc.knowledge_base_id,
                    operation_type=DocumentOperationType.retry_succeeded,
                    status='success',
                    task_id=task_id,
                    stage='processing',
                    message='文档重试处理完成',
                )

            _publish(task_id, doc.id, DocumentStatus.completed, 100, '文档处理完成')
        except Exception as e:
            logger.exception('document task failed document_id=%s task_id=%s error=%s', doc.id, task_id, e)
            doc.status = DocumentStatus.failed.value
            doc.error_message = str(e)
            doc.processing_finished_at = datetime.utcnow()
            db.commit()
            total_elapsed_ms = _log_step('process_document_task_total', task_started_at, document_id=doc.id, task_id=task_id, status='failed')
            DocumentService.create_operation_log(
                db,
                document_id=doc.id,
                knowledge_base_id=doc.knowledge_base_id,
                operation_type=DocumentOperationType.process_failed,
                status='failed',
                task_id=task_id,
                stage='processing',
                elapsed_ms=total_elapsed_ms,
                message=str(e),
            )
            if doc.retry_count > 0:
                DocumentService.create_operation_log(
                    db,
                    document_id=doc.id,
                    knowledge_base_id=doc.knowledge_base_id,
                    operation_type=DocumentOperationType.retry_failed,
                    status='failed',
                    task_id=task_id,
                    stage='processing',
                    message=str(e),
                )
            publish_progress(task_id, doc.id, DocumentStatus.failed, 100, f'任务失败: {e}')
            raise


@celery_app.task(name='app.tasks.document_tasks.delete_document_task', bind=True)
def delete_document_task(self, document_id: int):
    settings = get_settings()
    engine = create_engine(settings.db_url, future=True)

    logger.info('document delete task started document_id=%s db_url=%s', document_id, settings.db_url)
    task_started_at = perf_counter()

    with Session(engine) as db:
        doc = db.scalar(select(Document).where(Document.id == document_id))
        if not doc:
            logger.warning('document delete task aborted because document not found document_id=%s', document_id)
            return

        task_id = self.request.id
        doc.delete_task_id = task_id
        doc.status = DocumentStatus.deleting.value
        db.commit()
        db.refresh(doc)
        _publish(task_id, doc.id, DocumentStatus.deleting, 10, '删除任务已接收，开始清理文档数据')

        try:
            _publish(task_id, doc.id, DocumentStatus.deleting, 35, '正在删除文档 chunk 数据')
            _publish(task_id, doc.id, DocumentStatus.deleting, 70, '正在删除向量索引与源文件')
            DocumentService.finalize_delete(db, document_id)
            total_elapsed_ms = _log_step('delete_document_task_total', task_started_at, document_id=doc.id, task_id=task_id, status='deleted')
            DocumentService.create_operation_log(
                db,
                document_id=doc.id,
                knowledge_base_id=doc.knowledge_base_id,
                operation_type=DocumentOperationType.delete_succeeded,
                status='success',
                task_id=task_id,
                stage='delete',
                elapsed_ms=total_elapsed_ms,
                message='文档删除完成',
            )
            _publish(task_id, doc.id, DocumentStatus.deleted, 100, '文档删除完成')
        except Exception as e:
            logger.exception('document delete task failed document_id=%s task_id=%s error=%s', doc.id, task_id, e)
            failed_doc = DocumentService.mark_delete_failed(db, document_id, str(e))
            total_elapsed_ms = _log_step('delete_document_task_total', task_started_at, document_id=failed_doc.id, task_id=task_id, status='delete_failed')
            DocumentService.create_operation_log(
                db,
                document_id=failed_doc.id,
                knowledge_base_id=failed_doc.knowledge_base_id,
                operation_type=DocumentOperationType.delete_failed,
                status='failed',
                task_id=task_id,
                stage='delete',
                elapsed_ms=total_elapsed_ms,
                message=str(e),
            )
            _publish(task_id, failed_doc.id, DocumentStatus.delete_failed, 100, f'删除失败: {e}')
            raise
