from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.kb_member import KnowledgeBaseMember, MemberRole
from app.models.knowledge_base import KnowledgeBase


class KnowledgeBaseService:
    # 知识库服务：负责创建知识库、列出用户可见知识库以及成员校验。
    @staticmethod
    def create_kb(db: Session, owner_id: int, name: str, description: str | None, is_public: bool, system_prompt: str) -> KnowledgeBase:
        # 创建知识库并自动把创建者加入为 owner。
        kb = KnowledgeBase(
            owner_id=owner_id,
            name=name,
            description=description,
            is_public=is_public,
            system_prompt=system_prompt,
        )
        db.add(kb)
        db.flush()

        member = KnowledgeBaseMember(knowledge_base_id=kb.id, user_id=owner_id, role=MemberRole.owner)
        db.add(member)
        db.commit()
        db.refresh(kb)
        return kb

    @staticmethod
    def list_my_kbs(db: Session, user_id: int) -> list[KnowledgeBase]:
        # 查询当前用户参与的所有知识库，按创建顺序倒序返回。
        stmt = (
            select(KnowledgeBase)
            .join(KnowledgeBaseMember, KnowledgeBaseMember.knowledge_base_id == KnowledgeBase.id)
            .where(KnowledgeBaseMember.user_id == user_id)
            .order_by(KnowledgeBase.id.desc())
        )
        return list(db.scalars(stmt).all())

    @staticmethod
    def get_member(db: Session, kb_id: int, user_id: int) -> KnowledgeBaseMember | None:
        # 查询用户在指定知识库中的成员记录，用于权限判断。
        stmt = select(KnowledgeBaseMember).where(
            KnowledgeBaseMember.knowledge_base_id == kb_id,
            KnowledgeBaseMember.user_id == user_id,
        )
        return db.scalar(stmt)
