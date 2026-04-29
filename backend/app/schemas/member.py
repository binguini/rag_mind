from datetime import datetime

from pydantic import BaseModel

from app.models.kb_member import MemberRole


class MemberAddRequest(BaseModel):
    user_id: int
    role: MemberRole


class MemberUpdateRequest(BaseModel):
    role: MemberRole


class MemberResponse(BaseModel):
    id: int
    knowledge_base_id: int
    user_id: int
    role: MemberRole
    created_at: datetime
