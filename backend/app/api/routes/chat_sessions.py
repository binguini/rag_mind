import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id, get_db_session
from app.models.chat_session import ChatSessionStatus
from app.schemas.chat_session import (
    ChatMessageItem,
    ChatSessionCreateRequest,
    ChatSessionItem,
    ChatSessionUpdateRequest,
    ChatStreamRequest,
)
from app.services.chat_session_service import ChatSessionService
from app.services.kb_service import KnowledgeBaseService

router = APIRouter(prefix='/chat/sessions', tags=['chat_sessions'])
# 聊天会话相关接口：负责会话管理、消息查询和流式发送。


@router.get('', response_model=list[ChatSessionItem])
def list_chat_sessions(
    mode: str | None = Query(default=None),
    knowledge_base_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
):
    return ChatSessionService.list_sessions(db, user_id, mode=mode, knowledge_base_id=knowledge_base_id, status=status)


@router.get('/{session_id}', response_model=ChatSessionItem)
def get_chat_session(
    session_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
):
    session = ChatSessionService.get_session(db, session_id, user_id)
    if not session or session.status == ChatSessionStatus.DELETED.value:
        raise HTTPException(status_code=404, detail='会话不存在')
    return ChatSessionService._serialize_session(session)


@router.post('', response_model=ChatSessionItem)
def create_chat_session(
    payload: ChatSessionCreateRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
):
    if payload.mode.value == 'rag':
        if not payload.knowledge_base_id:
            raise HTTPException(status_code=422, detail='知识库会话必须指定 knowledge_base_id')
        member = KnowledgeBaseService.get_member(db, payload.knowledge_base_id, user_id)
        if not member:
            raise HTTPException(status_code=403, detail='无权限访问该知识库')
    return ChatSessionService.create_session(
        db,
        user_id,
        payload.mode,
        knowledge_base_id=payload.knowledge_base_id,
        title=payload.title,
    )


@router.get('/{session_id}/messages', response_model=list[ChatMessageItem])
def list_chat_messages(
    session_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
):
    session = ChatSessionService.get_session(db, session_id, user_id)
    if not session or session.status == 'deleted':
        raise HTTPException(status_code=404, detail='会话不存在')
    return ChatSessionService.list_messages(db, session_id, user_id)


@router.patch('/{session_id}', response_model=ChatSessionItem)
def update_chat_session(
    session_id: int,
    payload: ChatSessionUpdateRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
):
    session = ChatSessionService.get_session(db, session_id, user_id)
    if not session:
        raise HTTPException(status_code=404, detail='会话不存在')
    return ChatSessionService.update_session(db, session, title=payload.title, status=payload.status)


@router.delete('/{session_id}')
def delete_chat_session(
    session_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
):
    session = ChatSessionService.get_session(db, session_id, user_id)
    if not session:
        raise HTTPException(status_code=404, detail='会话不存在')
    ChatSessionService.update_session(db, session, status=ChatSessionStatus.DELETED)
    return {'ok': True}


@router.post('/{session_id}/stream')
def stream_chat_session(
    session_id: int,
    payload: ChatStreamRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
):
    session = ChatSessionService.get_session(db, session_id, user_id)
    if not session or session.status == 'deleted':
        raise HTTPException(status_code=404, detail='会话不存在')
    if session.mode == 'rag':
        member = KnowledgeBaseService.get_member(db, session.knowledge_base_id, user_id)
        if not member:
            raise HTTPException(status_code=403, detail='无权限访问该知识库')

    def event_stream():
        for event in ChatSessionService.stream_message(db, session, payload.message):
            yield f'data: {json.dumps(event, ensure_ascii=False)}\n\n'

    return StreamingResponse(event_stream(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})
