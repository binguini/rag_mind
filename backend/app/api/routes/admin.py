from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id, get_db_session
from app.schemas.model_config import ModelConfigResponse, ModelConfigUpdate
from app.services.config_service import ConfigService
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService

router = APIRouter(prefix='/admin', tags=['admin'])


@router.get('/model-config', response_model=ModelConfigResponse)
def get_model_config(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
):
    return ModelConfigResponse(
        llm_provider=ConfigService.get_value(db, 'llm_provider'),
        llm_model=ConfigService.get_value(db, 'llm_model'),
        llm_base_url=ConfigService.get_value(db, 'llm_base_url'),
        llm_api_key=ConfigService.get_value(db, 'llm_api_key'),
        embedding_provider=ConfigService.get_value(db, 'embedding_provider'),
        embedding_model_name=ConfigService.get_value(db, 'embedding_model_name'),
        retrieval_top_k=int(ConfigService.get_value(db, 'retrieval_top_k')),
        retrieval_threshold=float(ConfigService.get_value(db, 'retrieval_threshold')),
        history_window=int(ConfigService.get_value(db, 'history_window')),
        qwen_api_key=ConfigService.get_value(db, 'qwen_api_key'),
        ernie_api_key=ConfigService.get_value(db, 'ernie_api_key'),
    )


@router.put('/model-config', response_model=ModelConfigResponse)
def update_model_config(
    payload: ModelConfigUpdate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
):
    updates = payload.model_dump(exclude_none=True)
    for key, value in updates.items():
        ConfigService.set_value(db, key, str(value))
    return ModelConfigResponse(
        llm_provider=ConfigService.get_value(db, 'llm_provider'),
        llm_model=ConfigService.get_value(db, 'llm_model'),
        llm_base_url=ConfigService.get_value(db, 'llm_base_url'),
        llm_api_key=ConfigService.get_value(db, 'llm_api_key'),
        embedding_provider=ConfigService.get_value(db, 'embedding_provider'),
        embedding_model_name=ConfigService.get_value(db, 'embedding_model_name'),
        retrieval_top_k=int(ConfigService.get_value(db, 'retrieval_top_k')),
        retrieval_threshold=float(ConfigService.get_value(db, 'retrieval_threshold')),
        history_window=int(ConfigService.get_value(db, 'history_window')),
        qwen_api_key=ConfigService.get_value(db, 'qwen_api_key'),
        ernie_api_key=ConfigService.get_value(db, 'ernie_api_key'),
    )


@router.post('/test-llm')
def test_llm(payload: dict, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db_session)):
    try:
        return LLMService.test_connection(
            payload['provider'],
            payload.get('api_key', ''),
            payload.get('base_url'),
            payload.get('model'),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/test-embedding')
def test_embedding(payload: dict, user_id: int = Depends(get_current_user_id)):
    try:
        return EmbeddingService.test_connection(payload['provider'], payload.get('api_key', ''))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
