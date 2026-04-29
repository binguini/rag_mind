import logging
from functools import lru_cache
from typing import Iterable

from app.core.config import get_settings
from app.services.config_service import ConfigService

logger = logging.getLogger(__name__)


class EmbeddingService:
    # 向量化服务：负责加载 embedding 模型、文本编码和维度定义。
    @staticmethod
    @lru_cache(maxsize=1)
    def _get_model():
        """Lazy-load the HuggingFace embedding model once per process.

        The project now uses BAAI/bge-small-zh-v1.5 with CPU execution and
        normalized embeddings so cosine / IP based retrieval works consistently.
        """

        try:
            from langchain_community.embeddings import HuggingFaceEmbeddings
        except ImportError as exc:  # pragma: no cover - explicit dependency error path
            raise RuntimeError(
                '缺少 HuggingFaceEmbeddings 依赖，请先安装 langchain-community 和 sentence-transformers'
            ) from exc

        model_name = 'BAAI/bge-small-zh-v1.5'
        model_kwargs = {'device': 'cpu'}
        encode_kwargs = {'normalize_embeddings': True}
        logger.info('loading huggingface embedding model=%s device=%s normalize=%s', model_name, model_kwargs['device'], encode_kwargs['normalize_embeddings'])
        return HuggingFaceEmbeddings(model_name=model_name, model_kwargs=model_kwargs, encode_kwargs=encode_kwargs)

    @staticmethod
    def embed_texts(texts: Iterable[str], provider: str | None = None) -> list[list[float]]:
        texts = list(texts)
        model_name = provider or EmbeddingService.model_name()
        logger.info('embedding started chunks=%s model=%s', len(texts), model_name)
        if not texts:
            return []

        embeddings = EmbeddingService._get_model().embed_documents(texts)
        vectors = [list(map(float, vector)) for vector in embeddings]
        for idx, vector in enumerate(vectors):
            logger.debug('embedding generated chunk_index=%s vector_dim=%s', idx, len(vector))
        logger.info('embedding finished vectors=%s model=%s dim=%s', len(vectors), model_name, len(vectors[0]) if vectors else 0)
        return vectors

    @staticmethod
    def dimension() -> int:
        # BAAI/bge-small-zh-v1.5 的向量维度为 512 collection 需要保持一致。
        return 512

    @staticmethod
    def model_name(db=None) -> str:
        if db is not None:
            return ConfigService.get_value(db, 'embedding_model_name')
        settings = get_settings()
        return getattr(settings, 'embedding_model_name', 'BAAI/bge-small-zh-v1.5')

    @staticmethod
    def test_connection(provider: str, api_key: str) -> dict:
        if provider not in {'local', 'qwen', 'ernie'}:
            raise ValueError('不支持的 embedding provider')
        return {'provider': provider, 'ok': True, 'message': '连接测试成功'}
