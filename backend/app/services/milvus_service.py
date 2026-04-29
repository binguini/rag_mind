from pymilvus import connections, utility

from app.core.config import get_settings


class MilvusService:
    # Milvus 连接检测服务：用于健康检查和环境连通性确认。
    @staticmethod
    def check_connection() -> dict:
        settings = get_settings()
        kwargs = {'uri': settings.milvus_uri, 'db_name': settings.milvus_db_name}
        if settings.milvus_token:
            kwargs['token'] = settings.milvus_token

        connections.connect(alias='default', **kwargs)
        version = utility.get_server_version(using='default')
        return {'connected': True, 'server_version': version, 'uri': settings.milvus_uri}
