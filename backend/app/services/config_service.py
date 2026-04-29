from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crypto import decrypt_string, encrypt_string
from app.models.system_config import SystemConfig


# 系统配置默认值：覆盖模型、检索、调试和密钥等基础运行参数。
DEFAULTS = {
    'llm_provider': 'openai_compatible',
    'llm_model': 'gpt-4o-mini',
    'llm_base_url': 'https://xiaoai.plus/v1',
    'llm_api_key': '',
    'embedding_provider': 'local',
    'embedding_model_name': 'bge-small-zh',
    'retrieval_top_k': '8',
    'retrieval_threshold': '0.65',
    'history_window': '4',
    'qwen_api_key': '',
    'ernie_api_key': '',
    'rag_debug_enabled': 'false',
    'rag_debug_allowed_user_ids': '',
}

ENCRYPTED_KEYS = {'llm_api_key', 'qwen_api_key', 'ernie_api_key'}


class ConfigService:
    # 系统配置服务：统一读取、写入和加密保存配置项。
    @staticmethod
    def get_value(db: Session, key: str) -> str:
        # 单项读取配置，若数据库未设置则回退到默认值。
        row = db.scalar(select(SystemConfig).where(SystemConfig.key == key))
        if row:
            if row.is_encrypted and row.value:
                return decrypt_string(row.value)
            return row.value
        return DEFAULTS.get(key, '')

    @staticmethod
    def get_all(db: Session) -> dict[str, str]:
        # 读取全部配置并与默认值合并，供设置页一次性展示。
        values = DEFAULTS.copy()
        rows = db.scalars(select(SystemConfig)).all()
        for row in rows:
            values[row.key] = decrypt_string(row.value) if row.is_encrypted and row.value else row.value
        return values

    @staticmethod
    def set_value(db: Session, key: str, value: str, is_encrypted: bool | None = None) -> None:
        # 写入配置时按需加密敏感字段。
        encrypted = key in ENCRYPTED_KEYS if is_encrypted is None else is_encrypted
        stored_value = encrypt_string(value) if encrypted and value else value
        row = db.scalar(select(SystemConfig).where(SystemConfig.key == key))
        if row:
            row.value = stored_value
            row.is_encrypted = encrypted
        else:
            row = SystemConfig(key=key, value=stored_value, is_encrypted=encrypted)
            db.add(row)
        db.commit()
