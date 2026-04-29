from pydantic import BaseModel, Field


class RagQueryRequest(BaseModel):
    knowledge_base_id: int = Field(gt=0)
    question: str = Field(min_length=1)


class CitationItem(BaseModel):
    document_id: int
    document_name: str
    chunk_id: int
    chunk_index: int
    page: int | None = None
    score: float
    content: str


class RagQueryResponse(BaseModel):
    answer: str
    citations: list[CitationItem]
