from app.services.config_service import ConfigService


class BaseLLMAdapter:
    # LLM 适配器基类，统一封装不同模型提供方的流式输出接口。
    def stream_answer(self, prompt: str | None = None, messages: list[dict[str, str]] | None = None):
        raise NotImplementedError


class OpenAICompatibleLLMAdapter(BaseLLMAdapter):
    # 兼容 OpenAI API 的通用模型适配器。
    def __init__(self, db):
        self.db = db

    def stream_answer(self, prompt: str | None = None, messages: list[dict[str, str]] | None = None):
        from app.services.llm_service import LLMService

        yield from LLMService.stream_answer(
            prompt=prompt,
            messages=messages,
            provider=ConfigService.get_value(self.db, 'llm_provider'),
            model=ConfigService.get_value(self.db, 'llm_model'),
            base_url=ConfigService.get_value(self.db, 'llm_base_url'),
            api_key=ConfigService.get_value(self.db, 'llm_api_key'),
        )


class LocalLLMAdapter(BaseLLMAdapter):
    # 本地模型适配器，统一走同一套流式调用逻辑。
    def __init__(self, db):
        self.db = db

    def stream_answer(self, prompt: str | None = None, messages: list[dict[str, str]] | None = None):
        from app.services.llm_service import LLMService

        yield from LLMService.stream_answer(prompt=prompt, messages=messages, provider='local', model='local')


class BaseEmbeddingAdapter:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class LocalEmbeddingAdapter(BaseEmbeddingAdapter):
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        from app.services.embedding_service import EmbeddingService

        return EmbeddingService.embed_texts(texts, provider='local')


class AdapterFactory:
    # 适配器工厂：根据配置返回当前可用的 LLM / Embedding 实现。
    @staticmethod
    def llm(db):
        provider = ConfigService.get_value(db, 'llm_provider')
        if provider == 'local':
            return LocalLLMAdapter(db)
        return OpenAICompatibleLLMAdapter(db)

    @staticmethod
    def embedding(db):
        provider = ConfigService.get_value(db, 'embedding_provider')
        return LocalEmbeddingAdapter() if provider == 'local' else LocalEmbeddingAdapter()
