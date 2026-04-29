from pydantic import BaseModel, Field


class ModelConfigResponse(BaseModel):
    llm_provider: str
    llm_model: str
    llm_base_url: str
    llm_api_key: str
    embedding_provider: str
    embedding_model_name: str
    retrieval_top_k: int
    retrieval_threshold: float
    history_window: int
    qwen_api_key: str
    ernie_api_key: str


class ModelConfigUpdate(BaseModel):
    llm_provider: str | None = Field(default=None)
    llm_model: str | None = Field(default=None)
    llm_base_url: str | None = Field(default=None)
    llm_api_key: str | None = Field(default=None)
    embedding_provider: str | None = Field(default=None)
    embedding_model_name: str | None = Field(default=None)
    retrieval_top_k: int | None = Field(default=None, ge=1, le=50)
    retrieval_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    history_window: int | None = Field(default=None, ge=0, le=20)
    qwen_api_key: str | None = None
    ernie_api_key: str | None = None
