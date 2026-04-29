from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models.kb_member import KnowledgeBaseMember, MemberRole

# 统一从请求头中读取 Bearer Token，用于用户身份识别。
security = HTTPBearer(auto_error=True)


def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> int:
    # 校验访问令牌并返回当前用户 ID；失败时统一抛出 401。
    token = credentials.credentials
    try:
        payload = decode_token(token)
        if payload.get('type') != 'access':
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='令牌类型错误')
        sub = payload.get('sub')
        if sub is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='无效令牌')
        return int(sub)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='认证失败')


def get_db_session(db: Session = Depends(get_db)) -> Session:
    # 统一注入数据库会话，方便路由层直接使用。
    return db


def require_kb_role(db: Session, kb_id: int, user_id: int, allowed_roles: set[MemberRole]) -> KnowledgeBaseMember:
    # 校验当前用户在指定知识库中的角色权限。
    member = db.scalar(
        select(KnowledgeBaseMember).where(
            KnowledgeBaseMember.knowledge_base_id == kb_id,
            KnowledgeBaseMember.user_id == user_id,
        )
    )
    if not member or member.role not in allowed_roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='无权限访问该知识库')
    return member
