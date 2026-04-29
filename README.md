# RAG Mind

一个基于 RAG 架构的 AI 知识库问答系统，支持多知识库、文档上传解析、向量检索、混合检索、流式问答、模型配置与 Windows 本地开发。

## 当前实现概览

### 已完成的核心能力
- 用户注册 / 登录 / 刷新令牌
- JWT 鉴权与 bcrypt 密码加密
- 知识库创建与列表管理
- 知识库成员管理（owner / admin / editor / viewer）
- 文档上传（txt / pdf）
- 文件 MD5 去重
- 文档状态机：pending / running / completed / failed
- Celery + Redis 异步任务骨架
- WebSocket 文档任务进度推送
- 文档解析、分块、写入 Milvus 的基础链路
- RAG 检索、rerank、query rewrite、SSE 流式问答
- 模型与检索参数配置页
- API Key 加密存储
- Windows 本地开发适配
- Linux Docker 部署基础模板

### 技术栈
- 前端：Vue 3 + Vite + TypeScript + Element Plus + Pinia
- 后端：FastAPI + SQLAlchemy + Pydantic Settings
- 异步任务：Celery + Redis
- 向量库：Milvus
- 关系库：SQLite（开发）/ MySQL（生产）
- 文件存储：本地磁盘 / MinIO / OSS（可扩展）
