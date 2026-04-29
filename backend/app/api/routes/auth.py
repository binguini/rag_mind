from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
    UserProfileResponse,
    UserProfileUpdateRequest,
    UserResponse,
)
from app.services.auth_service import AuthService
from app.services.debug_access_service import DebugAccessService
from app.api.deps import get_current_user_id

router = APIRouter(prefix='/auth', tags=['auth'])


@router.post('/register', response_model=UserResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db_session)):
    try:
        user = AuthService.register(db, payload.username, payload.password)
        return UserResponse(id=user.id, username=user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/login', response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db_session)):
    try:
        access_token, refresh_token = AuthService.login(db, payload.username, payload.password)
        return TokenResponse(access_token=access_token, refresh_token=refresh_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post('/refresh', response_model=TokenResponse)
def refresh(payload: RefreshTokenRequest, db: Session = Depends(get_db_session)):
    try:
        access_token, refresh_token = AuthService.refresh_access_token(db, payload.refresh_token)
        return TokenResponse(access_token=access_token, refresh_token=refresh_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get('/me', response_model=UserProfileResponse)
def get_me(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db_session)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail='用户不存在')
    policy = DebugAccessService.get_policy(db, user.id)
    return UserProfileResponse(
        id=user.id,
        username=user.username,
        avatar_url=user.avatar_url,
        nickname=user.nickname,
        signature=user.signature,
        debug_access_enabled=policy['can_access'],
    )


@router.put('/me', response_model=UserProfileResponse)
def update_me(
    payload: UserProfileUpdateRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail='用户不存在')
    user.avatar_url = payload.avatar_url
    user.nickname = payload.nickname
    user.signature = payload.signature
    db.add(user)
    db.commit()
    db.refresh(user)
    policy = DebugAccessService.get_policy(db, user.id)
    return UserProfileResponse(
        id=user.id,
        username=user.username,
        avatar_url=user.avatar_url,
        nickname=user.nickname,
        signature=user.signature,
        debug_access_enabled=policy['can_access'],
    )
