from fastapi import APIRouter

from app.api.routes import admin, auth, chat_sessions, debug_admin, documents, kb_members, knowledge_base, rag, rag_debug

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(knowledge_base.router)
api_router.include_router(kb_members.router)
api_router.include_router(documents.router)
api_router.include_router(rag.router)
api_router.include_router(rag_debug.router)
api_router.include_router(chat_sessions.router)
api_router.include_router(admin.router)
api_router.include_router(debug_admin.router)
