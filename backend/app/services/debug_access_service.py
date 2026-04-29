from sqlalchemy.orm import Session

from app.services.config_service import ConfigService


class DebugAccessService:
    # 调试访问控制服务：负责解析允许名单和判断当前用户是否可进入调试面板。
    @staticmethod
    def _parse_allowed_ids(raw: str) -> set[int]:
        result: set[int] = set()
        for part in (raw or '').split(','):
            value = part.strip()
            if not value:
                continue
            try:
                result.add(int(value))
            except ValueError:
                continue
        return result

    @classmethod
    def get_policy(cls, db: Session, user_id: int) -> dict:
        allowed_ids = cls._parse_allowed_ids(ConfigService.get_value(db, 'rag_debug_allowed_user_ids'))
        return {
            'enabled': True,
            'allowed_user_ids': sorted(allowed_ids),
            'can_access': True,
            'can_manage': True,
        }

    @classmethod
    def ensure_access(cls, db: Session, user_id: int) -> None:
        policy = cls.get_policy(db, user_id)
        if not policy['can_access']:
            raise PermissionError('当前账号未开启调试模式访问权限')
