from pydantic import BaseModel, Field


class DebugAccessPolicyResponse(BaseModel):
    enabled: bool
    allowed_user_ids: list[int]
    can_access: bool
    can_manage: bool


class DebugAccessPolicyUpdate(BaseModel):
    enabled: bool
    allowed_user_ids: list[int] = Field(default_factory=list)
