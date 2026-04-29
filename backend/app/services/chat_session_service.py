from __future__ import annotations

import json
import logging
import time
from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.chat_message import ChatMessage, ChatMessageStatus, ChatRole
from app.models.chat_session import ChatMode, ChatSession, ChatSessionStatus
from app.models.knowledge_base import KnowledgeBase
from app.schemas.chat_session import ChatMessageItem, ChatSessionItem
from app.services.adapter_factory import AdapterFactory
from app.services.debug_access_service import DebugAccessService
from app.services.prompt_service import PromptService
from app.services.rag_debug_service import RAGDebugService
from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)


class ChatSessionService:
    # 聊天会话服务：负责会话生命周期、消息持久化、流式回复与 RAG/通用模式分流。
    @staticmethod
    def _build_session_title(title: str | None, first_message: str | None = None) -> str:
        if title and title.strip():
            return title.strip()[:200]
        if first_message and first_message.strip():
            return first_message.strip().replace('\n', ' ')[:40]
        return '新对话'

    @staticmethod
    def _serialize_session(session: ChatSession) -> ChatSessionItem:
        # 将会话 ORM 对象转换成前端可直接显示的结构。
        return ChatSessionItem(
            id=session.id,
            mode=ChatMode(session.mode),
            knowledge_base_id=session.knowledge_base_id,
            title=session.title,
            summary=session.summary,
            status=ChatSessionStatus(session.status),
            message_count=session.message_count,
            last_message_at=session.last_message_at,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )

    @staticmethod
    def _serialize_message(message: ChatMessage) -> ChatMessageItem:
        # 将消息 ORM 对象转换成前端展示结构，并还原 JSON 字段。
        citations = json.loads(message.citations_json) if message.citations_json else []
        meta = json.loads(message.meta_json) if message.meta_json else None
        return ChatMessageItem(
            id=message.id,
            session_id=message.session_id,
            role=ChatRole(message.role),
            content=message.content,
            content_type=message.content_type,
            status=ChatMessageStatus(message.status),
            citations=citations,
            meta=meta,
            error_message=message.error_message,
            parent_message_id=message.parent_message_id,
            created_at=message.created_at,
            updated_at=message.updated_at,
        )

    @staticmethod
    def create_session(db: Session, user_id: int, mode: ChatMode, knowledge_base_id: int | None = None, title: str | None = None) -> ChatSessionItem:
        # 新建一个聊天会话，并初始化为激活状态。
        session = ChatSession(
            user_id=user_id,
            mode=mode.value,
            knowledge_base_id=knowledge_base_id,
            title=ChatSessionService._build_session_title(title),
            status=ChatSessionStatus.ACTIVE.value,
            last_message_at=datetime.utcnow(),
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return ChatSessionService._serialize_session(session)

    @staticmethod
    def list_sessions(
        db: Session,
        user_id: int,
        mode: str | None = None,
        knowledge_base_id: int | None = None,
        status: str | None = None,
    ) -> list[ChatSessionItem]:
        # 查询当前用户的会话列表，并支持模式/知识库/状态筛选。
        stmt = select(ChatSession).where(ChatSession.user_id == user_id)
        if mode:
            stmt = stmt.where(ChatSession.mode == mode)
        if knowledge_base_id:
            stmt = stmt.where(ChatSession.knowledge_base_id == knowledge_base_id)
        if status:
            stmt = stmt.where(ChatSession.status == status)
        else:
            stmt = stmt.where(ChatSession.status != ChatSessionStatus.DELETED.value)
        stmt = stmt.order_by(desc(ChatSession.last_message_at), desc(ChatSession.id))
        sessions = db.scalars(stmt).all()
        return [ChatSessionService._serialize_session(item) for item in sessions]

    @staticmethod
    def get_session(db: Session, session_id: int, user_id: int) -> ChatSession | None:
        return db.scalar(select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id))

    @staticmethod
    def update_session(db: Session, session: ChatSession, title: str | None = None, status: ChatSessionStatus | None = None) -> ChatSessionItem:
        if title is not None:
            session.title = ChatSessionService._build_session_title(title)
        if status is not None:
            session.status = status.value
        session.updated_at = datetime.utcnow()
        db.add(session)
        db.commit()
        db.refresh(session)
        return ChatSessionService._serialize_session(session)

    @staticmethod
    def list_messages(db: Session, session_id: int, user_id: int) -> list[ChatMessageItem]:
        session = ChatSessionService.get_session(db, session_id, user_id)
        if not session:
            return []
        stmt = select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at, ChatMessage.id)
        messages = db.scalars(stmt).all()
        return [ChatSessionService._serialize_message(item) for item in messages]

    @staticmethod
    def _estimate_text_tokens(text: str) -> int:
        stripped = text.strip()
        if not stripped:
            return 0
        return max(1, len(stripped) // 4)

    @staticmethod
    def _trim_history_by_budget(history: list[dict], max_tokens: int = 3000) -> list[dict]:
        # 按 token 预算裁剪历史消息，避免上下文超长。
        kept: list[dict] = []
        budget = 0
        for item in reversed(history):
            cost = ChatSessionService._estimate_text_tokens(item.get('content', '')) + 8
            if kept and budget + cost > max_tokens:
                break
            kept.append(item)
            budget += cost
        return list(reversed(kept))

    @staticmethod
    def _build_history_for_model(db: Session, session_id: int, limit: int = 12) -> list[dict]:
        # 读取最近的已完成消息，拼成模型可用的上下文历史。
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id, ChatMessage.status.in_([ChatMessageStatus.DONE.value, ChatMessageStatus.CANCELLED.value]))
            .order_by(desc(ChatMessage.created_at), desc(ChatMessage.id))
        )
        rows = list(reversed(db.scalars(stmt.limit(limit)).all()))
        history: list[dict] = []
        for row in rows:
            if row.role in {ChatRole.USER.value, ChatRole.ASSISTANT.value, ChatRole.SYSTEM.value} and row.content:
                history.append({'role': row.role, 'content': row.content})
        return ChatSessionService._trim_history_by_budget(history)

    @staticmethod
    def _build_general_messages(history: list[dict], message: str) -> list[dict[str, str]]:
        # 构造通用聊天模式下的模型消息序列。
        messages: list[dict[str, str]] = [
            {'role': 'system', 'content': '你是一个专业、简洁、准确的助手。请结合上下文继续回答，保持清晰和直接。'}
        ]
        for item in history:
            role = item.get('role')
            content = (item.get('content') or '').strip()
            if role in {ChatRole.USER.value, ChatRole.ASSISTANT.value, ChatRole.SYSTEM.value} and content:
                messages.append({'role': role, 'content': content})
        messages.append({'role': 'user', 'content': message})
        return messages

    @staticmethod
    def _build_rag_prompt(db: Session, session: ChatSession, message: str, history: list[dict]) -> tuple[str, list[dict], str, dict]:
        # RAG 模式下先执行检索，再用知识库系统提示词组装最终 Prompt。
        retrieval = RAGService.retrieve(db, session.knowledge_base_id, message, history, session_id=session.id)
        kb = db.scalar(select(KnowledgeBase).where(KnowledgeBase.id == session.knowledge_base_id))
        system_prompt = kb.system_prompt if kb and kb.system_prompt else '你是一个专业的知识库问答助手。'
        prompt = PromptService.build_prompt(system_prompt, retrieval['rewritten_question'], retrieval['citations'], history=history)
        return prompt, retrieval['citations'], retrieval['rewritten_question'], retrieval

    @staticmethod
    def stream_message(db: Session, session: ChatSession, message: str):
        # 流式发送一条消息：先落库，再调用模型并持续返回 token。
        request_started_at = time.perf_counter()
        clean_message = message.strip()
        if not clean_message:
            raise ValueError('消息不能为空')

        if session.mode == ChatMode.RAG.value and not session.knowledge_base_id:
            raise ValueError('知识库会话缺少 knowledge_base_id')

        if session.title == '新对话':
            session.title = ChatSessionService._build_session_title(None, clean_message)

        persist_started_at = time.perf_counter()
        user_message = ChatMessage(
            session_id=session.id,
            role=ChatRole.USER.value,
            content=clean_message,
            status=ChatMessageStatus.DONE.value,
        )
        db.add(user_message)
        db.flush()

        assistant_message = ChatMessage(
            session_id=session.id,
            role=ChatRole.ASSISTANT.value,
            content='',
            status=ChatMessageStatus.STREAMING.value,
        )
        db.add(assistant_message)
        db.flush()

        session.message_count += 2
        session.last_message_at = datetime.utcnow()
        session.updated_at = datetime.utcnow()
        db.add(session)
        db.commit()
        db.refresh(assistant_message)
        db.refresh(session)
        persist_elapsed_ms = (time.perf_counter() - persist_started_at) * 1000

        yield {'type': 'message_start', 'message_id': assistant_message.id}

        history_started_at = time.perf_counter()
        history = ChatSessionService._build_history_for_model(db, session.id)
        history_elapsed_ms = (time.perf_counter() - history_started_at) * 1000
        citations: list[dict] = []
        meta: dict = {'mode': session.mode}
        answer = ''
        first_token_at: float | None = None
        first_token_elapsed_ms: float | None = None

        try:
            llm = AdapterFactory.llm(db)
            if session.mode == ChatMode.GENERAL.value:
                llm_messages = ChatSessionService._build_general_messages(history[:-1], clean_message)
                for token in llm.stream_answer(messages=llm_messages):
                    answer += token
                    if first_token_at is None:
                        first_token_at = time.perf_counter()
                        first_token_elapsed_ms = (first_token_at - request_started_at) * 1000
                    yield {'type': 'delta', 'message_id': assistant_message.id, 'content': token}
            else:
                prompt, citations, rewritten_question, retrieval = ChatSessionService._build_rag_prompt(db, session, clean_message, history[:-1])
                meta['rewritten_question'] = rewritten_question
                meta['rag_debug'] = {
                    'retrieval_params': retrieval['retrieval_params'],
                    'retrieved_hits': retrieval['retrieved_hits'],
                    'rerank_before': retrieval['rerank_before'],
                    'rerank_after': retrieval['rerank_after'],
                    'prompt_context': retrieval['prompt_context'],
                }
                for token in llm.stream_answer(prompt=prompt):
                    answer += token
                    if first_token_at is None:
                        first_token_at = time.perf_counter()
                        first_token_elapsed_ms = (first_token_at - request_started_at) * 1000
                    yield {'type': 'delta', 'message_id': assistant_message.id, 'content': token}

            assistant_message.content = answer
            assistant_message.status = ChatMessageStatus.DONE.value
            assistant_message.citations_json = json.dumps(citations, ensure_ascii=False) if citations else None
            meta['timings'] = {
                'persist_ms': round(persist_elapsed_ms, 2),
                'history_ms': round(history_elapsed_ms, 2),
                'first_token_ms': round(first_token_elapsed_ms or 0.0, 2),
                'total_ms': round((time.perf_counter() - request_started_at) * 1000, 2),
            }
            if session.mode == ChatMode.RAG.value:
                meta['rag_debug']['prompt_text'] = prompt
            assistant_message.meta_json = json.dumps(meta, ensure_ascii=False)
            assistant_message.updated_at = datetime.utcnow()
            session.last_message_at = datetime.utcnow()
            session.updated_at = datetime.utcnow()
            db.add(assistant_message)
            db.add(session)
            db.commit()

            if session.mode == ChatMode.RAG.value and DebugAccessService.get_policy(db, session.user_id)['can_access']:
                RAGDebugService.create_debug_log(
                    db,
                    {
                        'knowledge_base_id': session.knowledge_base_id,
                        'session_id': session.id,
                        'user_id': session.user_id,
                        'question': clean_message,
                        'rewritten_question': meta.get('rewritten_question'),
                        'answer': answer,
                        'retrieval_params_json': json.dumps(meta.get('rag_debug', {}).get('retrieval_params'), ensure_ascii=False),
                        'retrieved_hits_json': json.dumps(meta.get('rag_debug', {}).get('retrieved_hits', []), ensure_ascii=False),
                        'rerank_before_json': json.dumps(meta.get('rag_debug', {}).get('rerank_before', []), ensure_ascii=False),
                        'rerank_after_json': json.dumps(meta.get('rag_debug', {}).get('rerank_after', []), ensure_ascii=False),
                        'prompt_context_json': json.dumps(meta.get('rag_debug', {}).get('prompt_context', []), ensure_ascii=False),
                        'prompt_text': meta.get('rag_debug', {}).get('prompt_text'),
                        'citations_json': json.dumps(citations, ensure_ascii=False),
                        'generation_stage': 'completed',
                        'total_duration_ms': int(round((time.perf_counter() - request_started_at) * 1000, 2)),
                    },
                )

            logger.info(
                'chat_stream_completed session_id=%s mode=%s persist_ms=%.2f history_ms=%.2f first_token_ms=%.2f total_ms=%.2f answer_chars=%s',
                session.id,
                session.mode,
                persist_elapsed_ms,
                history_elapsed_ms,
                first_token_elapsed_ms or 0.0,
                (time.perf_counter() - request_started_at) * 1000,
                len(answer),
            )

            yield {
                'type': 'message_end',
                'message_id': assistant_message.id,
                'answer': answer,
                'citations': citations,
            }
        except Exception as exc:
            assistant_message.status = ChatMessageStatus.FAILED.value
            assistant_message.error_message = str(exc)
            assistant_message.updated_at = datetime.utcnow()
            db.add(assistant_message)
            db.commit()
            if session.mode == ChatMode.RAG.value and DebugAccessService.get_policy(db, session.user_id)['can_access']:
                RAGDebugService.create_debug_log(
                    db,
                    {
                        'knowledge_base_id': session.knowledge_base_id,
                        'session_id': session.id,
                        'user_id': session.user_id,
                        'question': clean_message,
                        'rewritten_question': meta.get('rewritten_question'),
                        'answer': answer or None,
                        'retrieval_params_json': json.dumps(meta.get('rag_debug', {}).get('retrieval_params'), ensure_ascii=False) if meta.get('rag_debug') else None,
                        'retrieved_hits_json': json.dumps(meta.get('rag_debug', {}).get('retrieved_hits', []), ensure_ascii=False) if meta.get('rag_debug') else None,
                        'rerank_before_json': json.dumps(meta.get('rag_debug', {}).get('rerank_before', []), ensure_ascii=False) if meta.get('rag_debug') else None,
                        'rerank_after_json': json.dumps(meta.get('rag_debug', {}).get('rerank_after', []), ensure_ascii=False) if meta.get('rag_debug') else None,
                        'prompt_context_json': json.dumps(meta.get('rag_debug', {}).get('prompt_context', []), ensure_ascii=False) if meta.get('rag_debug') else None,
                        'prompt_text': meta.get('rag_debug', {}).get('prompt_text') if meta.get('rag_debug') else None,
                        'citations_json': json.dumps(citations, ensure_ascii=False) if citations else None,
                        'generation_stage': 'failed',
                        'error_message': str(exc),
                        'total_duration_ms': int(round((time.perf_counter() - request_started_at) * 1000, 2)),
                    },
                )
            logger.exception('chat_stream_failed session_id=%s mode=%s', session.id, session.mode)
            yield {'type': 'error', 'message_id': assistant_message.id, 'error': str(exc)}
