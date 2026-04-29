from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id, get_db_session
from app.models.kb_member import MemberRole
from app.schemas.rag import RagQueryRequest, RagQueryResponse, CitationItem
from app.services.document_service import DocumentService
from app.services.kb_service import KnowledgeBaseService
from app.services.rag_service import RAGService

router = APIRouter(prefix='/rag', tags=['rag'])


@router.post('/query', response_model=RagQueryResponse)
def query_rag(
    payload: RagQueryRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
):
    member = KnowledgeBaseService.get_member(db, payload.knowledge_base_id, user_id)
    if not member:
        raise HTTPException(status_code=403, detail='无权限访问该知识库')

    answer, citations = RAGService.answer_question(db, payload.knowledge_base_id, user_id, payload.question)
    return RagQueryResponse(
        answer=answer,
        citations=[CitationItem(**item) for item in citations],
    )
