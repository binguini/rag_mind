import json
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.rag_record import RAGQueryRecord
from app.services.adapter_factory import AdapterFactory
from app.services.debug_access_service import DebugAccessService
from app.services.embedding_service import EmbeddingService
from app.services.prompt_service import PromptService
from app.services.query_rewrite_service import QueryRewriteService
from app.services.rag_debug_service import RAGDebugService
from app.services.rerank_service import RerankService
from app.services.vector_store_service import VectorStoreService


class RAGService:
    # RAG 主流程服务：负责重写、检索、rerank、Prompt 构建与调试日志写入。
    @staticmethod
    def _build_prompt_context(citations: list[dict]) -> list[dict[str, Any]]:
        # 将引用来源裁剪成适合 Prompt 注入的上下文结构。
        return [
            {
                'document_id': item.get('document_id'),
                'document_name': item.get('document_name'),
                'chunk_id': item.get('chunk_id'),
                'chunk_index': item.get('chunk_index'),
                'page': item.get('page'),
                'score': item.get('score'),
                'content': item.get('content'),
                'heading': item.get('heading'),
                'heading_path': item.get('heading_path'),
                'chunk_type': item.get('chunk_type'),
            }
            for item in citations
        ]

    @staticmethod
    def retrieve(
        db: Session,
        knowledge_base_id: int,
        question: str,
        history: list[dict] | None = None,
        session_id: int | None = None,
    ) -> dict[str, Any]:
        # 执行一次完整的检索链路，并返回前端调试页需要的所有中间结果。
        rewrite_started_at = time.perf_counter()
        rewritten_question = QueryRewriteService.rewrite(question, history)
        rewrite_duration_ms = round((time.perf_counter() - rewrite_started_at) * 1000)

        config, scope, _ = RAGDebugService.get_retrieval_config(db, knowledge_base_id, session_id=session_id)

        embedding_started_at = time.perf_counter()
        vector = EmbeddingService.embed_texts([rewritten_question])[0]
        embedding_duration_ms = round((time.perf_counter() - embedding_started_at) * 1000)

        retrieval_started_at = time.perf_counter()
        hits = VectorStoreService.hybrid_search(
            db,
            knowledge_base_id,
            rewritten_question,
            vector,
            top_k=int(config['top_k']),
        )
        retrieval_duration_ms = round((time.perf_counter() - retrieval_started_at) * 1000)
        rerank_before = [dict(item) for item in hits]

        rerank_started_at = time.perf_counter()
        reranked = RerankService.rerank(rewritten_question, hits) if config.get('rerank_enabled', True) else hits
        rerank_duration_ms = round((time.perf_counter() - rerank_started_at) * 1000)

        citations: list[dict] = []
        for hit in reranked[: int(config['top_k'])]:
            if hit.get('fusion_score', 0.0) < float(config['threshold']):
                continue
            chunk = db.scalar(select(DocumentChunk).where(DocumentChunk.id == hit['chunk_id']))
            doc = db.scalar(select(Document).where(Document.id == hit['document_id']))
            if not chunk or not doc:
                continue

            metadata = json.loads(chunk.metadata_json) if chunk.metadata_json else {}
            citations.append(
                {
                    'document_id': doc.id,
                    'document_name': doc.filename,
                    'chunk_id': chunk.id,
                    'chunk_index': chunk.chunk_index,
                    'page': chunk.source_page,
                    'score': hit.get('fusion_score', hit.get('score', 0.0)),
                    'content': chunk.content[:300],
                    'heading': metadata.get('heading'),
                    'heading_path': metadata.get('heading_path'),
                    'chunk_type': metadata.get('chunk_type'),
                    'match_reason': {
                        'vector_score': hit.get('vector_score', 0.0),
                        'bm25_score': hit.get('bm25_score', 0.0),
                        'fusion_score': hit.get('fusion_score', hit.get('score', 0.0)),
                    },
                }
            )

        return {
            'rewritten_question': rewritten_question,
            'citations': citations,
            'retrieval_params': {**config, 'scope': scope},
            'retrieved_hits': hits,
            'rerank_before': rerank_before,
            'rerank_after': reranked,
            'prompt_context': RAGService._build_prompt_context(citations),
            'timings': {
                'rewrite_duration_ms': rewrite_duration_ms,
                'embedding_duration_ms': embedding_duration_ms,
                'retrieval_duration_ms': retrieval_duration_ms,
                'rerank_duration_ms': rerank_duration_ms,
            },
        }

    @staticmethod
    def stream_answer(
        db: Session,
        knowledge_base_id: int,
        user_id: int,
        question: str,
        history: list[dict] | None = None,
        session_id: int | None = None,
    ):
        # 流式回答入口：先完成检索，再构造 Prompt 并将 LLM 输出逐 token 返回前端。
        started_at = time.perf_counter()
        retrieval = RAGService.retrieve(db, knowledge_base_id, question, history, session_id=session_id)
        rewritten_question = retrieval['rewritten_question']
        citations = retrieval['citations']
        kb_prompt = '你是一个专业的知识库问答助手。'

        prompt_build_started_at = time.perf_counter()
        prompt = PromptService.build_prompt(kb_prompt, rewritten_question, citations)
        prompt_build_duration_ms = round((time.perf_counter() - prompt_build_started_at) * 1000)

        llm = AdapterFactory.llm(db)
        answer = ''
        for token in llm.stream_answer(prompt):
            answer += token
            yield {'type': 'delta', 'content': token}

        yield {
            'type': 'final',
            'answer': answer,
            'citations': citations,
            'debug': {
                **retrieval,
                'prompt_text': prompt,
                'prompt_build_duration_ms': prompt_build_duration_ms,
            },
        }

        db.add(
            RAGQueryRecord(
                knowledge_base_id=knowledge_base_id,
                user_id=user_id,
                question=question,
                answer=answer,
                citations_json=json.dumps(citations, ensure_ascii=False),
            )
        )
        if DebugAccessService.get_policy(db, user_id)['can_access']:
            RAGDebugService.create_debug_log(
                db,
                {
                    'knowledge_base_id': knowledge_base_id,
                    'session_id': session_id,
                    'user_id': user_id,
                    'question': question,
                    'rewritten_question': rewritten_question,
                    'answer': answer,
                    'retrieval_params_json': json.dumps(retrieval['retrieval_params'], ensure_ascii=False),
                    'retrieved_hits_json': json.dumps(retrieval['retrieved_hits'], ensure_ascii=False),
                    'rerank_before_json': json.dumps(retrieval['rerank_before'], ensure_ascii=False),
                    'rerank_after_json': json.dumps(retrieval['rerank_after'], ensure_ascii=False),
                    'prompt_context_json': json.dumps(retrieval['prompt_context'], ensure_ascii=False),
                    'prompt_text': prompt,
                    'citations_json': json.dumps(citations, ensure_ascii=False),
                    'generation_stage': 'completed',
                    'total_duration_ms': round((time.perf_counter() - started_at) * 1000),
                    'rewrite_duration_ms': retrieval['timings']['rewrite_duration_ms'],
                    'embedding_duration_ms': retrieval['timings']['embedding_duration_ms'],
                    'retrieval_duration_ms': retrieval['timings']['retrieval_duration_ms'],
                    'rerank_duration_ms': retrieval['timings']['rerank_duration_ms'],
                    'prompt_build_duration_ms': prompt_build_duration_ms,
                },
            )
