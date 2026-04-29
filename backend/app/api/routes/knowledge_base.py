from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id, get_db_session
from app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseResponse
from app.services.kb_service import KnowledgeBaseService

router = APIRouter(prefix='/knowledge-bases', tags=['knowledge_bases'])


@router.get('', response_model=list[KnowledgeBaseResponse])
def list_my_knowledge_bases(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
):
    records = KnowledgeBaseService.list_my_kbs(db, user_id)
    return [
        KnowledgeBaseResponse(
            id=r.id,
            owner_id=r.owner_id,
            name=r.name,
            description=r.description,
            is_public=r.is_public,
            system_prompt=r.system_prompt,
            created_at=r.created_at,
        )
        for r in records
    ]


@router.post('', response_model=KnowledgeBaseResponse)
def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
):
    kb = KnowledgeBaseService.create_kb(
        db=db,
        owner_id=user_id,
        name=payload.name,
        description=payload.description,
        is_public=payload.is_public,
        system_prompt=payload.system_prompt,
    )
    return KnowledgeBaseResponse(
        id=kb.id,
        owner_id=kb.owner_id,
        name=kb.name,
        description=kb.description,
        is_public=kb.is_public,
        system_prompt=kb.system_prompt,
        created_at=kb.created_at,
    )
