from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MemberRole(str, Enum):
    owner = 'owner'
    admin = 'admin'
    editor = 'editor'
    viewer = 'viewer'


class KnowledgeBaseMember(Base):
    __tablename__ = 'knowledge_base_members'
    __table_args__ = (UniqueConstraint('knowledge_base_id', 'user_id', name='uq_kb_user'),)

    id: Mapped[int] = mapped_column(primary_key=True)
    knowledge_base_id: Mapped[int] = mapped_column(ForeignKey('knowledge_bases.id'), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    role: Mapped[MemberRole] = mapped_column(SAEnum(MemberRole), default=MemberRole.viewer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
