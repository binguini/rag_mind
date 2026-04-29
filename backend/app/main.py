import asyncio
import logging
import sys

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from app.api.router import api_router
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import engine
from app import models  # noqa: F401
from app.services.milvus_service import MilvusService
from app.services.progress_service import progress_channel
from app.services.ws_manager import ws_manager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
)
logging.getLogger('uvicorn').setLevel(logging.INFO)
logging.getLogger('uvicorn.error').setLevel(logging.INFO)
logging.getLogger('uvicorn.access').setLevel(logging.INFO)

settings = get_settings()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(',') if origin.strip()],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(api_router, prefix=settings.api_prefix)


def _ensure_user_profile_columns():
    with engine.begin() as conn:
        dialect = conn.dialect.name
        if dialect == 'sqlite':
            existing = {row[1] for row in conn.exec_driver_sql('PRAGMA table_info(users)').fetchall()}
            for column_sql, column_name in [
                ('ALTER TABLE users ADD COLUMN avatar_url VARCHAR(500)', 'avatar_url'),
                ('ALTER TABLE users ADD COLUMN nickname VARCHAR(80)', 'nickname'),
                ('ALTER TABLE users ADD COLUMN signature TEXT', 'signature'),
            ]:
                if column_name not in existing:
                    conn.exec_driver_sql(column_sql)


def _ensure_document_columns():
    with engine.begin() as conn:
        dialect = conn.dialect.name
        if dialect != 'sqlite':
            return

        existing = {row[1] for row in conn.exec_driver_sql('PRAGMA table_info(documents)').fetchall()}
        for column_sql, column_name in [
            ('ALTER TABLE documents ADD COLUMN page_count INTEGER DEFAULT 0', 'page_count'),
            ('ALTER TABLE documents ADD COLUMN extracted_preview TEXT', 'extracted_preview'),
            ('ALTER TABLE documents ADD COLUMN processing_started_at DATETIME', 'processing_started_at'),
            ('ALTER TABLE documents ADD COLUMN processing_finished_at DATETIME', 'processing_finished_at'),
            ('ALTER TABLE documents ADD COLUMN retry_count INTEGER DEFAULT 0', 'retry_count'),
            ('ALTER TABLE documents ADD COLUMN delete_task_id VARCHAR(100)', 'delete_task_id'),
            ('ALTER TABLE documents ADD COLUMN delete_source_file_requested BOOLEAN DEFAULT 0', 'delete_source_file_requested'),
        ]:
            if column_name not in existing:
                conn.exec_driver_sql(column_sql)


def _ensure_document_operation_log_table():
    with engine.begin() as conn:
        dialect = conn.dialect.name
        if dialect != 'sqlite':
            return

        existing_tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if 'document_operation_logs' not in existing_tables:
            conn.exec_driver_sql(
                '''
                CREATE TABLE document_operation_logs (
                    id INTEGER NOT NULL PRIMARY KEY,
                    document_id INTEGER NOT NULL,
                    knowledge_base_id INTEGER NOT NULL,
                    operator_user_id INTEGER,
                    operation_type VARCHAR(50) NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'success',
                    task_id VARCHAR(100),
                    stage VARCHAR(50),
                    elapsed_ms INTEGER,
                    message TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                '''
            )
            conn.exec_driver_sql('CREATE INDEX ix_document_operation_logs_document_id ON document_operation_logs (document_id)')
            conn.exec_driver_sql('CREATE INDEX ix_document_operation_logs_knowledge_base_id ON document_operation_logs (knowledge_base_id)')
            conn.exec_driver_sql('CREATE INDEX ix_document_operation_logs_operator_user_id ON document_operation_logs (operator_user_id)')
            conn.exec_driver_sql('CREATE INDEX ix_document_operation_logs_operation_type ON document_operation_logs (operation_type)')
            conn.exec_driver_sql('CREATE INDEX ix_document_operation_logs_status ON document_operation_logs (status)')
            conn.exec_driver_sql('CREATE INDEX ix_document_operation_logs_task_id ON document_operation_logs (task_id)')
            conn.exec_driver_sql('CREATE INDEX ix_document_operation_logs_stage ON document_operation_logs (stage)')
            conn.exec_driver_sql('CREATE INDEX ix_document_operation_logs_created_at ON document_operation_logs (created_at)')
            return

        existing_columns = {row[1] for row in conn.exec_driver_sql('PRAGMA table_info(document_operation_logs)').fetchall()}
        for column_sql, column_name in [
            ('ALTER TABLE document_operation_logs ADD COLUMN stage VARCHAR(50)', 'stage'),
            ('ALTER TABLE document_operation_logs ADD COLUMN elapsed_ms INTEGER', 'elapsed_ms'),
        ]:
            if column_name not in existing_columns:
                conn.exec_driver_sql(column_sql)


def _ensure_document_operation_log_indexes():
    with engine.begin() as conn:
        dialect = conn.dialect.name
        if dialect != 'sqlite':
            return
        indexes = {row[1] for row in conn.exec_driver_sql('PRAGMA index_list(document_operation_logs)').fetchall()}
        statements = [
            ('ix_document_operation_logs_document_id', 'CREATE INDEX ix_document_operation_logs_document_id ON document_operation_logs (document_id)'),
            ('ix_document_operation_logs_knowledge_base_id', 'CREATE INDEX ix_document_operation_logs_knowledge_base_id ON document_operation_logs (knowledge_base_id)'),
            ('ix_document_operation_logs_operator_user_id', 'CREATE INDEX ix_document_operation_logs_operator_user_id ON document_operation_logs (operator_user_id)'),
            ('ix_document_operation_logs_operation_type', 'CREATE INDEX ix_document_operation_logs_operation_type ON document_operation_logs (operation_type)'),
            ('ix_document_operation_logs_status', 'CREATE INDEX ix_document_operation_logs_status ON document_operation_logs (status)'),
            ('ix_document_operation_logs_task_id', 'CREATE INDEX ix_document_operation_logs_task_id ON document_operation_logs (task_id)'),
            ('ix_document_operation_logs_stage', 'CREATE INDEX ix_document_operation_logs_stage ON document_operation_logs (stage)'),
            ('ix_document_operation_logs_created_at', 'CREATE INDEX ix_document_operation_logs_created_at ON document_operation_logs (created_at)'),
        ]
        for name, sql in statements:
            if name not in indexes:
                conn.exec_driver_sql(sql)


def _ensure_rag_debug_log_table():
    with engine.begin() as conn:
        dialect = conn.dialect.name
        if dialect != 'sqlite':
            return

        existing_tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if 'rag_debug_logs' not in existing_tables:
            conn.exec_driver_sql(
                '''
                CREATE TABLE rag_debug_logs (
                    id INTEGER NOT NULL PRIMARY KEY,
                    knowledge_base_id INTEGER NOT NULL,
                    session_id INTEGER,
                    user_id INTEGER NOT NULL,
                    question TEXT NOT NULL,
                    rewritten_question TEXT,
                    answer TEXT,
                    retrieval_params_json TEXT,
                    retrieved_hits_json TEXT,
                    rerank_before_json TEXT,
                    rerank_after_json TEXT,
                    prompt_context_json TEXT,
                    prompt_text TEXT,
                    citations_json TEXT,
                    generation_stage VARCHAR(50),
                    error_message TEXT,
                    total_duration_ms INTEGER,
                    rewrite_duration_ms INTEGER,
                    embedding_duration_ms INTEGER,
                    retrieval_duration_ms INTEGER,
                    rerank_duration_ms INTEGER,
                    prompt_build_duration_ms INTEGER,
                    is_bad_case BOOLEAN DEFAULT 0,
                    bad_case_category VARCHAR(50),
                    bad_case_note TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                '''
            )
            return

        existing_columns = {row[1] for row in conn.exec_driver_sql('PRAGMA table_info(rag_debug_logs)').fetchall()}
        for column_sql, column_name in [
            ('ALTER TABLE rag_debug_logs ADD COLUMN bad_case_category VARCHAR(50)', 'bad_case_category'),
            ('ALTER TABLE rag_debug_logs ADD COLUMN bad_case_note TEXT', 'bad_case_note'),
        ]:
            if column_name not in existing_columns:
                conn.exec_driver_sql(column_sql)


def _ensure_rag_debug_log_indexes():
    with engine.begin() as conn:
        dialect = conn.dialect.name
        if dialect != 'sqlite':
            return
        indexes = {row[1] for row in conn.exec_driver_sql('PRAGMA index_list(rag_debug_logs)').fetchall()}
        statements = [
            ('ix_rag_debug_logs_knowledge_base_id', 'CREATE INDEX ix_rag_debug_logs_knowledge_base_id ON rag_debug_logs (knowledge_base_id)'),
            ('ix_rag_debug_logs_session_id', 'CREATE INDEX ix_rag_debug_logs_session_id ON rag_debug_logs (session_id)'),
            ('ix_rag_debug_logs_user_id', 'CREATE INDEX ix_rag_debug_logs_user_id ON rag_debug_logs (user_id)'),
            ('ix_rag_debug_logs_created_at', 'CREATE INDEX ix_rag_debug_logs_created_at ON rag_debug_logs (created_at)'),
        ]
        for name, sql in statements:
            if name not in indexes:
                conn.exec_driver_sql(sql)


@app.on_event('startup')
def on_startup():
    Base.metadata.create_all(bind=engine)
    _ensure_user_profile_columns()
    _ensure_document_columns()
    _ensure_document_operation_log_table()
    _ensure_document_operation_log_indexes()
    _ensure_rag_debug_log_table()
    _ensure_rag_debug_log_indexes()


@app.get('/health/live')
def live():
    return {'status': 'ok'}


@app.get('/health/ready')
def ready():
    milvus = MilvusService.check_connection()
    return {'status': 'ready', 'milvus': milvus}


@app.websocket('/ws/tasks/{task_id}')
async def task_progress_ws(websocket: WebSocket, task_id: str):
    channel = progress_channel(task_id)
    await ws_manager.connect(channel, websocket)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)

    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message.get('type') == 'message':
                await websocket.send_text(message['data'])
            await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.disconnect(channel, websocket)
        await pubsub.unsubscribe(channel)
        await pubsub.close()
        await redis.close()
