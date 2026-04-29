import json
import logging
from typing import Any

from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility

from app.core.config import get_settings
from app.services.config_service import ConfigService
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class VectorStoreService:
    # 向量库服务：负责 Milvus 连接、集合初始化、写入、删除和检索。
    collection_name = 'document_chunks'

    @staticmethod
    def connect() -> None:
        # 连接 Milvus；如配置了 token 一并带上。
        settings = get_settings()
        kwargs = {'uri': settings.milvus_uri, 'db_name': settings.milvus_db_name}
        if settings.milvus_token:
            kwargs['token'] = settings.milvus_token
        logger.info('connecting milvus uri=%s db=%s collection=%s', settings.milvus_uri, settings.milvus_db_name, VectorStoreService.collection_name)
        connections.connect(alias='default', **kwargs)

    @classmethod
    def ensure_collection(cls) -> Collection:
        # 若集合不存在则按当前 embedding 维度创建，并建立向量索引。
        cls.connect()
        dim = EmbeddingService.dimension()
        expected_model = EmbeddingService.model_name()
        if utility.has_collection(cls.collection_name):
            logger.info('milvus collection exists collection=%s dim=%s model=%s', cls.collection_name, dim, expected_model)
            return Collection(cls.collection_name)

        logger.info('creating milvus collection collection=%s dim=%s model=%s', cls.collection_name, dim, expected_model)
        fields = [
            FieldSchema(name='id', dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name='knowledge_base_id', dtype=DataType.INT64),
            FieldSchema(name='document_id', dtype=DataType.INT64),
            FieldSchema(name='chunk_id', dtype=DataType.INT64),
            FieldSchema(name='content', dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name='metadata_json', dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name='embedding', dtype=DataType.FLOAT_VECTOR, dim=dim),
        ]
        schema = CollectionSchema(fields=fields, description='RAG Mind document chunks')
        collection = Collection(cls.collection_name, schema=schema)
        collection.create_index(
            field_name='embedding',
            index_params={'index_type': 'HNSW', 'metric_type': 'IP', 'params': {'M': 8, 'efConstruction': 64}},
        )
        return collection

    @classmethod
    def insert_chunks(cls, rows: list[dict[str, Any]]) -> None:
        # 批量写入文档切片向量数据。
        if not rows:
            logger.warning('milvus insert skipped because rows empty')
            return
        logger.info('milvus insert started collection=%s rows=%s', cls.collection_name, len(rows))
        collection = cls.ensure_collection()
        collection.insert(rows)
        collection.flush()
        logger.info('milvus insert finished collection=%s rows=%s', cls.collection_name, len(rows))

    @classmethod
    def delete_document_chunks(cls, document_id: int) -> None:
        # 删除某个文档对应的全部向量切片。
        collection = cls.ensure_collection()
        expr = f'document_id == {document_id}'
        logger.info('milvus delete started collection=%s expr=%s', cls.collection_name, expr)
        collection.delete(expr)
        collection.flush()
        logger.info('milvus delete finished collection=%s expr=%s', cls.collection_name, expr)

    @classmethod
    def search(cls, knowledge_base_id: int, vector: list[float], top_k: int = 5) -> list[dict[str, Any]]:
        # 基于向量相似度检索当前知识库的候选切片。
        collection = cls.ensure_collection()
        collection.load()
        results = collection.search(
            data=[vector],
            anns_field='embedding',
            param={'metric_type': 'IP', 'params': {'ef': 64}},
            limit=top_k,
            expr=f'knowledge_base_id == {knowledge_base_id}',
            output_fields=['knowledge_base_id', 'document_id', 'chunk_id', 'content', 'metadata_json'],
        )
        payload: list[dict[str, Any]] = []
        for hit in results[0]:
            payload.append(
                {
                    'document_id': hit.entity.get('document_id'),
                    'chunk_id': hit.entity.get('chunk_id'),
                    'content': hit.entity.get('content'),
                    'metadata_json': hit.entity.get('metadata_json'),
                    'score': float(hit.score),
                    'source': 'vector',
                }
            )
        return payload

    @classmethod
    def hybrid_search(cls, db, knowledge_base_id: int, question: str, vector: list[float], top_k: int = 8) -> list[dict[str, Any]]:
        # 将向量检索结果与 BM25 结果合并，形成混合召回结果。
        vector_hits = cls.search(knowledge_base_id, vector, top_k=top_k)
        bm25_hits = []
        try:
            from app.services.bm25_service import BM25Service

            bm25_hits = BM25Service.search(db, knowledge_base_id, question, top_k=top_k)
        except Exception:
            bm25_hits = []

        merged: dict[int, dict[str, Any]] = {}
        for rank, hit in enumerate(vector_hits):
            merged[hit['chunk_id']] = {
                **hit,
                'vector_score': hit['score'],
                'bm25_score': 0.0,
                'fusion_score': 1.0 / (rank + 1),
            }

        for rank, hit in enumerate(bm25_hits):
            existing = merged.get(hit['chunk_id'])
            if existing:
                existing['bm25_score'] = hit['score']
                existing['fusion_score'] += 1.0 / (rank + 1)
            else:
                merged[hit['chunk_id']] = {
                    **hit,
                    'vector_score': 0.0,
                    'bm25_score': hit['score'],
                    'fusion_score': 1.0 / (rank + 1),
                }

        return sorted(merged.values(), key=lambda item: item['fusion_score'], reverse=True)[:top_k]
