from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables.

    The project uses a single settings object as the source of truth for:
    - API metadata and runtime mode
    - authentication token lifetimes
    - database / Redis / Celery connections
    - file upload storage
    - vector database connection details
    - browser CORS origins

    `extra='ignore'` allows newer deployments to carry additional env keys
    without breaking older code paths.
    """

    # Read values from backend/.env when present. Pydantic will still allow
    # environment variables and explicit overrides in production.
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    # Basic application metadata.
    app_name: str = 'RAG Mind API'
    app_env: str = 'dev'
    app_debug: bool = True
    api_prefix: str = '/api/v1'

    # Security-related defaults. These should be overridden in real deployments.
    secret_key: str = 'change_me_in_production'
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Local database connection string used by SQLAlchemy.
    db_url: str = 'sqlite:///./rag_mind.db'

    # Redis is used both as a cache / message broker and as the Celery backend.
    redis_url: str = 'redis://127.0.0.1:6379/0'
    celery_broker_url: str = 'redis://127.0.0.1:6379/0'
    celery_result_backend: str = 'redis://127.0.0.1:6379/1'

    # File storage and embedding defaults for document processing.
    upload_dir: str = './storage/uploads'

    # 默认使用 BAAI/bge-small-zh-v1.5 作为中文语义向量模型。
    # 如果后续切换到别的模型，只需要修改该配置，并同步 Milvus collection 的维度。
    embedding_model_name: str = 'BAAI/bge-small-zh-v1.5'

    # Milvus connection settings for vector search.
    milvus_uri: str = 'http://47.94.88.6:19530'
    milvus_token: str | None = None
    milvus_db_name: str = 'default'

    # Comma-separated list of allowed frontend origins.
    cors_origins: str = 'http://localhost:5173'


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance.

    Caching avoids repeatedly parsing environment variables and keeps the
    configuration object lightweight to import from anywhere in the app.
    """

    return Settings()
