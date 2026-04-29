from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id, get_db_session, require_kb_role
from app.models.kb_member import MemberRole
from app.schemas.member import MemberAddRequest, MemberResponse, MemberUpdateRequest
from app.services.member_service import MemberService

router = APIRouter(prefix='/knowledge-bases/{kb_id}/members', tags=['knowledge_base_members'])


@router.get('', response_model=list[MemberResponse])
def list_members(
    kb_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
):
    require_kb_role(db, kb_id, user_id, {MemberRole.owner, MemberRole.admin, MemberRole.editor, MemberRole.viewer})
    members = MemberService.list_members(db, kb_id)
    return [
        MemberResponse(
            id=m.id,
            knowledge_base_id=m.knowledge_base_id,
            user_id=m.user_id,
            role=m.role,
            created_at=m.created_at,
        )
        for m in members
    ]


@router.post('', response_model=MemberResponse)
def add_member(
    kb_id: int,
    payload: MemberAddRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
):
    require_kb_role(db, kb_id, user_id, {MemberRole.owner, MemberRole.admin})
    try:
        member = MemberService.add_member(db, kb_id, payload.user_id, payload.role)
        return MemberResponse(
            id=member.id,
            knowledge_base_id=member.knowledge_base_id,
            user_id=member.user_id,
            role=member.role,
            created_at=member.created_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch('/{member_user_id}', response_model=MemberResponse)
def update_member_role(
    kb_id: int,
    member_user_id: int,
    payload: MemberUpdateRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
):
    require_kb_role(db, kb_id, user_id, {MemberRole.owner, MemberRole.admin})
    try:
        member = MemberService.update_member_role(db, kb_id, member_user_id, payload.role)
        return MemberResponse(
            id=member.id,
            knowledge_base_id=member.knowledge_base_id,
            user_id=member.user_id,
            role=member.role,
            created_at=member.created_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete('/{member_user_id}')
def remove_member(
    kb_id: int,
    member_user_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
):
    require_kb_role(db, kb_id, user_id, {MemberRole.owner, MemberRole.admin})
    try:
        MemberService.remove_member(db, kb_id, member_user_id)
        return {'message': '成员已移除'}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
