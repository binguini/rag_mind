import asyncio
import json
import logging

import redis

from app.core.config import get_settings
from app.models.document import DocumentStatus
from app.services.ws_manager import ws_manager

logger = logging.getLogger(__name__)


def progress_channel(task_id: str) -> str:
    # 文档任务进度消息的 Redis / WebSocket 统一频道名。
    return f'doc_task:{task_id}'


def _infer_stage(message: str) -> str:
    # 根据进度文案推断当前处理阶段，便于前端展示更友好的状态标签。
    lowered = message.lower()
    if '删除完成' in message:
        return 'delete_completed'
    if '删除' in message and ('清理' in message or '向量' in message or '源文件' in message):
        return 'deleting'
    if '完成' in message and ('文档处理完成' in message or '向量入库完成' in message):
        return 'completed'
    if '切分' in message or '分块' in message:
        return 'chunking'
    if '写入 Milvus' in message or 'Milvus' in message or '入库' in message:
        return 'vector_store'
    if '向量' in message or 'embedding' in lowered:
        return 'embedding'
    if '解析' in message:
        return 'parsing'
    return 'processing'


async def _broadcast_websocket(task_id: str, payload: dict) -> None:
    await ws_manager.broadcast(progress_channel(task_id), payload)


def publish_progress(task_id: str, document_id: int, status: DocumentStatus, progress: int, message: str) -> None:
    # 同时向 Redis 和 WebSocket 推送文档任务进度。
    settings = get_settings()
    client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    payload = {
        'task_id': task_id,
        'document_id': document_id,
        'status': status.value,
        'progress': progress,
        'message': message,
        'stage': _infer_stage(message),
    }
    logger.info(
        'publish progress task_id=%s document_id=%s status=%s progress=%s message=%s',
        task_id,
        document_id,
        status.value,
        progress,
        message,
    )
    client.publish(progress_channel(task_id), json.dumps(payload, ensure_ascii=False))
    try:
        asyncio.get_running_loop().create_task(_broadcast_websocket(task_id, payload))
    except RuntimeError:
        logger.debug('no running event loop for websocket broadcast task_id=%s document_id=%s', task_id, document_id)
