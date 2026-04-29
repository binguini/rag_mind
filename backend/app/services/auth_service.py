from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, create_refresh_token, decode_token, get_password_hash, verify_password
from app.models.refresh_token import RefreshToken
from app.models.user import User


class AuthService:
    # 认证服务：负责用户注册、登录和刷新访问令牌。
    @staticmethod
    def register(db: Session, username: str, password: str) -> User:
        # 注册前先检查用户名是否重复。
        existing = db.scalar(select(User).where(User.username == username))
        if existing:
            raise ValueError('用户名已存在')

        user = User(username=username, password_hash=get_password_hash(password))
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def login(db: Session, username: str, password: str) -> tuple[str, str]:
        # 校验用户名和密码，成功后签发访问令牌与刷新令牌。
        user = db.scalar(select(User).where(User.username == username))
        if not user or not verify_password(password, user.password_hash):
            raise ValueError('用户名或密码错误')

        access_token = create_access_token(str(user.id))
        refresh_token, expires_at = create_refresh_token(str(user.id))

        db.add(RefreshToken(user_id=user.id, token=refresh_token, expires_at=expires_at))
        db.commit()
        return access_token, refresh_token

    @staticmethod
    def refresh_access_token(db: Session, refresh_token: str) -> tuple[str, str]:
        # 根据刷新令牌重新签发访问令牌，并让旧刷新令牌失效。
        payload = decode_token(refresh_token)
        if payload.get('type') != 'refresh':
            raise ValueError('令牌类型错误')

        sub = payload.get('sub')
        if sub is None:
            raise ValueError('令牌无效')

        token_row = db.scalar(select(RefreshToken).where(RefreshToken.token == refresh_token))
        if not token_row:
            raise ValueError('刷新令牌不存在')
        if token_row.revoked:
            raise ValueError('刷新令牌已失效')
        if token_row.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
            raise ValueError('刷新令牌已过期')

        token_row.revoked = True
        access_token = create_access_token(str(sub))
        new_refresh_token, expires_at = create_refresh_token(str(sub))
        db.add(RefreshToken(user_id=int(sub), token=new_refresh_token, expires_at=expires_at))
        db.commit()
        return access_token, new_refresh_token
