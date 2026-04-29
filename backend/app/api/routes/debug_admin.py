from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id, get_db_session
from app.schemas.debug_access import DebugAccessPolicyResponse, DebugAccessPolicyUpdate
from app.services.config_service import ConfigService
from app.services.debug_access_service import DebugAccessService

router = APIRouter(prefix='/admin/debug-access', tags=['debug_access'])


@router.get('', response_model=DebugAccessPolicyResponse)
def get_debug_access_policy(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
):
    policy = DebugAccessService.get_policy(db, user_id)
    if not policy['can_manage']:
        raise HTTPException(status_code=403, detail='当前账号无权查看调试开关配置')
    return DebugAccessPolicyResponse(**policy)


@router.put('', response_model=DebugAccessPolicyResponse)
def update_debug_access_policy(
    payload: DebugAccessPolicyUpdate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
):
    policy = DebugAccessService.get_policy(db, user_id)
    if not policy['can_manage']:
        raise HTTPException(status_code=403, detail='当前账号无权修改调试开关配置')
    ConfigService.set_value(db, 'rag_debug_enabled', 'true' if payload.enabled else 'false', is_encrypted=False)
    ConfigService.set_value(
        db,
        'rag_debug_allowed_user_ids',
        ','.join(str(item) for item in payload.allowed_user_ids),
        is_encrypted=False,
    )
    return DebugAccessPolicyResponse(**DebugAccessService.get_policy(db, user_id))
