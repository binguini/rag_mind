from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.kb_member import KnowledgeBaseMember, MemberRole
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User


class MemberService:
    # 成员服务：负责知识库成员的查询、添加、改角色与移除。
    @staticmethod
    def list_members(db: Session, kb_id: int) -> list[KnowledgeBaseMember]:
        stmt = (
            select(KnowledgeBaseMember)
            .where(KnowledgeBaseMember.knowledge_base_id == kb_id)
            .order_by(KnowledgeBaseMember.id.asc())
        )
        return list(db.scalars(stmt).all())

    @staticmethod
    def add_member(db: Session, kb_id: int, user_id: int, role: MemberRole) -> KnowledgeBaseMember:
        # 为知识库新增成员前，先校验知识库与用户是否存在。
        kb = db.scalar(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
        if not kb:
            raise ValueError('知识库不存在')

        user = db.scalar(select(User).where(User.id == user_id))
        if not user:
            raise ValueError('用户不存在')

        existing = db.scalar(
            select(KnowledgeBaseMember).where(
                KnowledgeBaseMember.knowledge_base_id == kb_id,
                KnowledgeBaseMember.user_id == user_id,
            )
        )
        if existing:
            raise ValueError('该用户已是成员')

        member = KnowledgeBaseMember(knowledge_base_id=kb_id, user_id=user_id, role=role)
        db.add(member)
        db.commit()
        db.refresh(member)
        return member

    @staticmethod
    def update_member_role(db: Session, kb_id: int, user_id: int, role: MemberRole) -> KnowledgeBaseMember:
        # 修改成员角色，禁止调整 owner 角色。
        member = db.scalar(
            select(KnowledgeBaseMember).where(
                KnowledgeBaseMember.knowledge_base_id == kb_id,
                KnowledgeBaseMember.user_id == user_id,
            )
        )
        if not member:
            raise ValueError('成员不存在')

        if member.role == MemberRole.owner:
            raise ValueError('不能修改 owner 角色')

        member.role = role
        db.commit()
        db.refresh(member)
        return member

    @staticmethod
    def remove_member(db: Session, kb_id: int, user_id: int) -> None:
        # 从知识库成员列表中移除指定用户，owner 不允许删除。
        member = db.scalar(
            select(KnowledgeBaseMember).where(
                KnowledgeBaseMember.knowledge_base_id == kb_id,
                KnowledgeBaseMember.user_id == user_id,
            )
        )
        if not member:
            raise ValueError('成员不存在')

        if member.role == MemberRole.owner:
            raise ValueError('不能删除 owner')

        db.delete(member)
        db.commit()
