import json
import logging
from pathlib import Path
from time import perf_counter

from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_operation_log import DocumentOperationType
from app.services.chunking_service import ChunkingService
from app.services.document_service import DocumentService
from app.services.embedding_service import EmbeddingService
from app.services.vector_store_service import VectorStoreService

logger = logging.getLogger(__name__)


class DocumentIndexService:
    # 文档索引服务：负责解析文档、切片、生成向量并写入向量库。
    @staticmethod
    def index_document(db: Session, document: Document) -> int:
        # 记录索引开始日志，便于排查文档处理耗时。
        logger.info(
            'indexing document started document_id=%s kb_id=%s filename=%s type=%s path=%s',
            document.id,
            document.knowledge_base_id,
            document.filename,
            document.file_type,
            document.file_path,
        )

        started_at = perf_counter()
        if document.file_type in {'txt', 'md'}:
            text = Path(document.file_path).read_text(encoding='utf-8', errors='ignore')
            pages = [text]
            logger.info('loaded %s for indexing document_id=%s chars=%s', document.file_type, document.id, len(text))
        elif document.file_type == 'pdf':
            from pypdf import PdfReader

            reader = PdfReader(document.file_path)
            pages = [page.extract_text() or '' for page in reader.pages]
            logger.info('loaded pdf for indexing document_id=%s pages=%s', document.id, len(pages))
        else:
            raise ValueError(f'不支持的文件类型: {document.file_type}')

        raw_text = '\n\n'.join(pages).strip()
        logger.info('document text prepared document_id=%s text_length=%s model=%s', document.id, len(raw_text), EmbeddingService.model_name())

        chunk_started_at = perf_counter()
        DocumentService.create_operation_log(
            db,
            document_id=document.id,
            knowledge_base_id=document.knowledge_base_id,
            operation_type=DocumentOperationType.chunking_started,
            status='running',
            task_id=document.task_id,
            stage='chunking',
            message='开始切分文档内容',
        )
        if document.file_type == 'md':
            structured_chunks = ChunkingService.split_markdown(raw_text, chunk_size=500, overlap=50)
            chunks = [item.text for item in structured_chunks]
        else:
            chunks = ChunkingService.split_text(raw_text, chunk_size=500, overlap=50)
            structured_chunks = None
        chunk_elapsed_ms = round((perf_counter() - chunk_started_at) * 1000)
        logger.info('text split completed document_id=%s chunks=%s', document.id, len(chunks))
        logger.info('index stage finished document_id=%s stage=chunking elapsed_ms=%s', document.id, chunk_elapsed_ms)
        DocumentService.create_operation_log(
            db,
            document_id=document.id,
            knowledge_base_id=document.knowledge_base_id,
            operation_type=DocumentOperationType.chunking_completed,
            status='success',
            task_id=document.task_id,
            stage='chunking',
            elapsed_ms=chunk_elapsed_ms,
            message=f'切分完成，生成 {len(chunks)} 个 chunk',
        )
        if not chunks:
            logger.warning('no chunks generated document_id=%s file_type=%s', document.id, document.file_type)
            raise ValueError('文档解析后未生成可检索切片')

        embedding_started_at = perf_counter()
        DocumentService.create_operation_log(
            db,
            document_id=document.id,
            knowledge_base_id=document.knowledge_base_id,
            operation_type=DocumentOperationType.embedding_started,
            status='running',
            task_id=document.task_id,
            stage='embedding',
            message='开始生成向量',
        )
        embeddings = EmbeddingService.embed_texts(chunks)
        embedding_elapsed_ms = round((perf_counter() - embedding_started_at) * 1000)
        logger.info('embedding generated document_id=%s vectors=%s dim=%s', document.id, len(embeddings), EmbeddingService.dimension())
        logger.info('index stage finished document_id=%s stage=embedding elapsed_ms=%s', document.id, embedding_elapsed_ms)
        DocumentService.create_operation_log(
            db,
            document_id=document.id,
            knowledge_base_id=document.knowledge_base_id,
            operation_type=DocumentOperationType.embedding_completed,
            status='success',
            task_id=document.task_id,
            stage='embedding',
            elapsed_ms=embedding_elapsed_ms,
            message=f'向量生成完成，共 {len(embeddings)} 条',
        )

        chunk_rows: list[dict] = []
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            logger.debug('prepare chunk document_id=%s chunk_index=%s chunk_length=%s', document.id, idx, len(chunk))
            chunk_meta = structured_chunks[idx] if structured_chunks else None
            metadata = {
                'document_id': document.id,
                'filename': document.filename,
                'chunk_index': idx,
                'file_md5': document.file_md5,
            }
            if chunk_meta:
                metadata.update(
                    {
                        'heading': chunk_meta.heading,
                        'heading_path': chunk_meta.heading_path,
                        'heading_level': chunk_meta.level,
                        'chunk_type': chunk_meta.chunk_type,
                    }
                )
            doc_chunk = DocumentChunk(
                document_id=document.id,
                knowledge_base_id=document.knowledge_base_id,
                chunk_index=idx,
                content=chunk,
                source_page=None,
                source_file=document.filename,
                metadata_json=json.dumps(metadata, ensure_ascii=False),
            )
            db.add(doc_chunk)
            db.flush()
            chunk_rows.append(
                {
                    'knowledge_base_id': document.knowledge_base_id,
                    'document_id': document.id,
                    'chunk_id': doc_chunk.id,
                    'content': chunk,
                    'metadata_json': doc_chunk.metadata_json or '{}',
                    'embedding': embedding,
                }
            )

        db_started_at = perf_counter()
        db.commit()
        logger.info('document chunks committed to sql document_id=%s rows=%s', document.id, len(chunk_rows))
        logger.info('index stage finished document_id=%s stage=sql_commit elapsed_ms=%s', document.id, round((perf_counter() - db_started_at) * 1000, 2))

        vector_started_at = perf_counter()
        DocumentService.create_operation_log(
            db,
            document_id=document.id,
            knowledge_base_id=document.knowledge_base_id,
            operation_type=DocumentOperationType.vector_store_started,
            status='running',
            task_id=document.task_id,
            stage='vector_store',
            message='开始写入向量库',
        )
        VectorStoreService.insert_chunks(chunk_rows)
        vector_elapsed_ms = round((perf_counter() - vector_started_at) * 1000)
        logger.info('document chunks inserted to vector store document_id=%s rows=%s', document.id, len(chunk_rows))
        logger.info('index stage finished document_id=%s stage=milvus_write elapsed_ms=%s', document.id, vector_elapsed_ms)
        DocumentService.create_operation_log(
            db,
            document_id=document.id,
            knowledge_base_id=document.knowledge_base_id,
            operation_type=DocumentOperationType.vector_store_completed,
            status='success',
            task_id=document.task_id,
            stage='vector_store',
            elapsed_ms=vector_elapsed_ms,
            message=f'向量库写入完成，共 {len(chunk_rows)} 条',
        )
        logger.info('index document total elapsed_ms=%s document_id=%s', round((perf_counter() - started_at) * 1000, 2), document.id)
        return len(chunks)
