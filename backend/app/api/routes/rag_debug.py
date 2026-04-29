from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id, get_db_session
from app.schemas.rag_debug import (
    RAGDebugLogItem,
    RAGDebugLogListResponse,
    RAGDebugLogMarkBadCasePayload,
    RetrievalConfigPayload,
    RetrievalConfigResponse,
)
from app.services.debug_access_service import DebugAccessService
from app.services.kb_service import KnowledgeBaseService
from app.services.rag_debug_service import RAGDebugService

router = APIRouter(prefix='/rag-debug', tags=['rag_debug'])
# RAG 调试相关接口：包含检索配置读取/保存、调试日志查询、bad case 标注和导出。


@router.get('/config', response_model=RetrievalConfigResponse)
@router.get('/config', response_model=RetrievalConfigResponse)
def get_retrieval_config(
    knowledge_base_id: int = Query(..., gt=0),
    session_id: int | None = Query(default=None, gt=0),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
):
    try:
        DebugAccessService.ensure_access(db, user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    member = KnowledgeBaseService.get_member(db, knowledge_base_id, user_id)
    if not member:
        raise HTTPException(status_code=403, detail='无权限访问该知识库')
    config, scope, updated_at = RAGDebugService.get_retrieval_config(db, knowledge_base_id, session_id=session_id)
    return RetrievalConfigResponse(
        scope=scope,
        knowledge_base_id=knowledge_base_id,
        session_id=session_id if scope == 'session' else None,
        updated_at=updated_at,
        **config,
    )


@router.put('/config', response_model=RetrievalConfigResponse)
def save_retrieval_config(
    payload: RetrievalConfigPayload,
    knowledge_base_id: int = Query(..., gt=0),
    session_id: int | None = Query(default=None, gt=0),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
):
    try:
        DebugAccessService.ensure_access(db, user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    member = KnowledgeBaseService.get_member(db, knowledge_base_id, user_id)
    if not member:
        raise HTTPException(status_code=403, detail='无权限访问该知识库')
    try:
        config, scope, updated_at = RAGDebugService.save_retrieval_config(
            db,
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
            payload=payload,
            session_id=session_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return RetrievalConfigResponse(
        scope=scope,
        knowledge_base_id=knowledge_base_id,
        session_id=session_id if scope == 'session' else None,
        updated_at=updated_at,
        **config,
    )


@router.get('/logs', response_model=RAGDebugLogListResponse)
def list_rag_debug_logs(
    knowledge_base_id: int | None = Query(default=None, gt=0),
    session_id: int | None = Query(default=None, gt=0),
    question: str | None = Query(default=None),
    is_bad_case: bool | None = Query(default=None),
    bad_case_category: str | None = Query(default=None),
    stage: str | None = Query(default=None),
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
):
    try:
        DebugAccessService.ensure_access(db, user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if knowledge_base_id:
        member = KnowledgeBaseService.get_member(db, knowledge_base_id, user_id)
        if not member:
            raise HTTPException(status_code=403, detail='无权限访问该知识库')
    items, total = RAGDebugService.list_debug_logs(
        db,
        user_id=user_id,
        knowledge_base_id=knowledge_base_id,
        session_id=session_id,
        question=question,
        is_bad_case=is_bad_case,
        bad_case_category=bad_case_category,
        stage=stage,
        start_at=start_at,
        end_at=end_at,
        limit=limit,
        offset=offset,
    )
    return RAGDebugLogListResponse(
        items=[RAGDebugLogItem(**item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.patch('/logs/{log_id}/bad-case', response_model=RAGDebugLogItem)
def mark_bad_case(
    log_id: int,
    payload: RAGDebugLogMarkBadCasePayload,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
):
    try:
        DebugAccessService.ensure_access(db, user_id)
        item = RAGDebugService.mark_bad_case(
            db,
            log_id,
            user_id=user_id,
            is_bad_case=payload.is_bad_case,
            bad_case_category=payload.bad_case_category,
            bad_case_note=payload.bad_case_note,
        )
        return RAGDebugLogItem(**item)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get('/logs/export')
def export_bad_cases(
    knowledge_base_id: int | None = Query(default=None, gt=0),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
):
    try:
        DebugAccessService.ensure_access(db, user_id)
        if knowledge_base_id:
            member = KnowledgeBaseService.get_member(db, knowledge_base_id, user_id)
            if not member:
                raise HTTPException(status_code=403, detail='无权限访问该知识库')
        content = RAGDebugService.export_bad_cases_csv(db, user_id=user_id, knowledge_base_id=knowledge_base_id)
        return Response(
            content=content,
            media_type='text/csv; charset=utf-8',
            headers={'Content-Disposition': 'attachment; filename=rag_bad_cases.csv'},
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
