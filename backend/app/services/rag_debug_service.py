import json
from datetime import datetime

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session

from app.models.chat_session import ChatSession
from app.models.knowledge_base import KnowledgeBase
from app.models.rag_debug import RAGDebugLog
from app.schemas.rag_debug import RetrievalConfigPayload


class RAGDebugService:
    # 调试面板专用服务：负责检索配置读写、调试日志序列化与 bad case 导出。
    DEFAULT_CONFIG = {
        'top_k': 8,
        'threshold': 0.2,
        'rerank_enabled': True,
        'chunk_size': 800,
        'chunk_overlap': 100,
    }

    @staticmethod
    def _parse_json(value: str | None, fallback):
        # 将数据库中存储的 JSON 字符串安全解析为 Python 对象；失败时返回兜底值。
        if not value:
            return fallback
        try:
            return json.loads(value)
        except Exception:
            return fallback

    @classmethod
    def get_retrieval_config(
        cls,
        db: Session,
        knowledge_base_id: int,
        session_id: int | None = None,
    ) -> tuple[dict, str, datetime | None]:
        # 优先读取会话级配置；如果没有，再回退到知识库级配置，最后返回默认值。
        if session_id:
            session = db.scalar(select(ChatSession).where(ChatSession.id == session_id, ChatSession.knowledge_base_id == knowledge_base_id))
            if session and session.summary:
                config = cls._parse_json(session.summary, None)
                if isinstance(config, dict) and config.get('retrieval_config'):
                    return {**cls.DEFAULT_CONFIG, **config['retrieval_config']}, 'session', session.updated_at

        kb = db.scalar(select(KnowledgeBase).where(KnowledgeBase.id == knowledge_base_id))
        if not kb:
            raise ValueError('知识库不存在')

        description_payload = cls._parse_json(kb.description, None)
        if isinstance(description_payload, dict) and description_payload.get('retrieval_config'):
            return {**cls.DEFAULT_CONFIG, **description_payload['retrieval_config']}, 'knowledge_base', kb.created_at

        return dict(cls.DEFAULT_CONFIG), 'knowledge_base', kb.created_at

    @classmethod
    def save_retrieval_config(
        cls,
        db: Session,
        user_id: int,
        knowledge_base_id: int,
        payload: RetrievalConfigPayload,
        session_id: int | None = None,
    ) -> tuple[dict, str, datetime | None]:
        # 根据作用域把配置写入会话摘要或知识库描述中，方便后续调试页面读取。
        config = {
            'top_k': payload.top_k,
            'threshold': payload.threshold,
            'rerank_enabled': payload.rerank_enabled,
            'chunk_size': payload.chunk_size,
            'chunk_overlap': payload.chunk_overlap,
        }

        if payload.scope == 'session':
            if not session_id:
                raise ValueError('会话级配置必须提供 session_id')
            session = db.scalar(select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id))
            if not session:
                raise ValueError('会话不存在')
            meta = cls._parse_json(session.summary, {}) if session.summary else {}
            meta['retrieval_config'] = config
            session.summary = json.dumps(meta, ensure_ascii=False)
            session.updated_at = datetime.utcnow()
            db.add(session)
            db.commit()
            db.refresh(session)
            return config, 'session', session.updated_at

        kb = db.scalar(select(KnowledgeBase).where(KnowledgeBase.id == knowledge_base_id))
        if not kb:
            raise ValueError('知识库不存在')
        meta = cls._parse_json(kb.description, {}) if kb.description else {}
        meta['retrieval_config'] = config
        kb.description = json.dumps(meta, ensure_ascii=False)
        db.add(kb)
        db.commit()
        db.refresh(kb)
        return config, 'knowledge_base', kb.created_at

    @staticmethod
    def create_debug_log(db: Session, payload: dict) -> RAGDebugLog:
        # 保存一次 RAG 调试链路的完整记录。
        row = RAGDebugLog(**payload)
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    @classmethod
    def serialize_debug_log(cls, row: RAGDebugLog) -> dict:
        # 将 ORM 记录转成前端可直接消费的字典结构。
        return {
            'id': row.id,
            'knowledge_base_id': row.knowledge_base_id,
            'session_id': row.session_id,
            'user_id': row.user_id,
            'question': row.question,
            'rewritten_question': row.rewritten_question,
            'answer': row.answer,
            'retrieval_params': cls._parse_json(row.retrieval_params_json, None),
            'retrieved_hits': cls._parse_json(row.retrieved_hits_json, []),
            'rerank_before': cls._parse_json(row.rerank_before_json, []),
            'rerank_after': cls._parse_json(row.rerank_after_json, []),
            'prompt_context': cls._parse_json(row.prompt_context_json, []),
            'prompt_text': row.prompt_text,
            'citations': cls._parse_json(row.citations_json, []),
            'generation_stage': row.generation_stage,
            'error_message': row.error_message,
            'total_duration_ms': row.total_duration_ms,
            'rewrite_duration_ms': row.rewrite_duration_ms,
            'embedding_duration_ms': row.embedding_duration_ms,
            'retrieval_duration_ms': row.retrieval_duration_ms,
            'rerank_duration_ms': row.rerank_duration_ms,
            'prompt_build_duration_ms': row.prompt_build_duration_ms,
            'is_bad_case': row.is_bad_case,
            'bad_case_category': row.bad_case_category,
            'bad_case_note': row.bad_case_note,
            'created_at': row.created_at,
        }

    @classmethod
    def list_debug_logs(
        cls,
        db: Session,
        user_id: int,
        knowledge_base_id: int | None = None,
        session_id: int | None = None,
        question: str | None = None,
        is_bad_case: bool | None = None,
        bad_case_category: str | None = None,
        stage: str | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        # 根据用户、知识库、会话和时间范围等条件分页查询调试日志。
        conditions = [RAGDebugLog.user_id == user_id]

        if knowledge_base_id:
            conditions.append(RAGDebugLog.knowledge_base_id == knowledge_base_id)
        if session_id:
            conditions.append(RAGDebugLog.session_id == session_id)
        if question:
            like_value = f'%{question}%'
            conditions.append(or_(RAGDebugLog.question.like(like_value), RAGDebugLog.rewritten_question.like(like_value)))
        if is_bad_case is not None:
            conditions.append(RAGDebugLog.is_bad_case == is_bad_case)
        if bad_case_category:
            conditions.append(RAGDebugLog.bad_case_category == bad_case_category)
        if stage:
            conditions.append(RAGDebugLog.generation_stage == stage)
        if start_at:
            conditions.append(RAGDebugLog.created_at >= start_at)
        if end_at:
            conditions.append(RAGDebugLog.created_at <= end_at)

        stmt = select(RAGDebugLog).where(and_(*conditions))
        count_stmt = select(func.count()).select_from(RAGDebugLog).where(and_(*conditions))

        total = int(db.scalar(count_stmt) or 0)
        rows = db.scalars(stmt.order_by(desc(RAGDebugLog.created_at), desc(RAGDebugLog.id)).offset(offset).limit(limit)).all()
        return [cls.serialize_debug_log(row) for row in rows], total

    @classmethod
    def mark_bad_case(
        cls,
        db: Session,
        log_id: int,
        user_id: int,
        is_bad_case: bool,
        bad_case_category: str | None = None,
        bad_case_note: str | None = None,
    ) -> dict:
        # 更新指定调试日志的 bad case 标记与备注。
        row = db.scalar(select(RAGDebugLog).where(RAGDebugLog.id == log_id, RAGDebugLog.user_id == user_id))
        if not row:
            raise ValueError('调试日志不存在')
        row.is_bad_case = is_bad_case
        row.bad_case_category = bad_case_category if is_bad_case else None
        row.bad_case_note = bad_case_note if is_bad_case else None
        db.add(row)
        db.commit()
        db.refresh(row)
        return cls.serialize_debug_log(row)

    @classmethod
    def export_bad_cases_csv(
        cls,
        db: Session,
        user_id: int,
        knowledge_base_id: int | None = None,
    ) -> str:
        # 导出当前用户的 bad case 列表为 CSV 文本。
        conditions = [RAGDebugLog.user_id == user_id, RAGDebugLog.is_bad_case.is_(True)]
        if knowledge_base_id:
            conditions.append(RAGDebugLog.knowledge_base_id == knowledge_base_id)
        rows = db.scalars(select(RAGDebugLog).where(and_(*conditions)).order_by(desc(RAGDebugLog.created_at), desc(RAGDebugLog.id))).all()

        lines = ['id,knowledge_base_id,session_id,category,question,rewritten_question,note,stage,created_at']
        for row in rows:
            values = [
                str(row.id),
                str(row.knowledge_base_id),
                str(row.session_id or ''),
                (row.bad_case_category or '').replace(',', '，').replace('\n', ' '),
                (row.question or '').replace(',', '，').replace('\n', ' '),
                (row.rewritten_question or '').replace(',', '，').replace('\n', ' '),
                (row.bad_case_note or '').replace(',', '，').replace('\n', ' '),
                (row.generation_stage or '').replace(',', '，').replace('\n', ' '),
                row.created_at.isoformat(),
            ]
            lines.append(','.join(values))
        return '\n'.join(lines)
