from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    'rag_mind',
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=False,
    # 本项目在本地开发环境经常只有 API 服务，没有单独启动 Celery worker。
    # 将任务改为 eager 模式后，.delay()/apply_async() 会直接在当前进程执行，
    # 这样文档上传后状态能够立即从 pending 进入 running/completed/failed，
    # 避免“文件已落盘，但数据库状态一直卡在等待中”的情况。
    task_always_eager=settings.app_env in {'dev', 'local'},
    task_eager_propagates=True,
)

celery_app.autodiscover_tasks(['app.tasks'])
