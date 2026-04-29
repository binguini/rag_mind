from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=3)
    password: str = Field(min_length=6)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3)
    password: str = Field(min_length=6)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = 'bearer'


class UserResponse(BaseModel):
    id: int
    username: str


class UserProfileResponse(BaseModel):
    id: int
    username: str
    avatar_url: str | None = None
    nickname: str | None = None
    signature: str | None = None
    debug_access_enabled: bool = False
    debug_access_enabled: bool = False


class UserProfileUpdateRequest(BaseModel):
    avatar_url: str | None = None
    nickname: str | None = Field(default=None, max_length=80)
    signature: str | None = Field(default=None, max_length=500)
