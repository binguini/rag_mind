import { apiClient } from './client'

export interface RetrievalConfigPayload {
  top_k: number
  threshold: number
  rerank_enabled: boolean
  chunk_size: number
  chunk_overlap: number
  scope: 'knowledge_base' | 'session'
}

export interface RetrievalConfigResponse extends RetrievalConfigPayload {
  knowledge_base_id: number | null
  session_id: number | null
  updated_at: string | null
}

export interface RAGDebugLogItem {
  id: number
  knowledge_base_id: number
  session_id: number | null
  user_id: number
  question: string
  rewritten_question: string | null
  answer: string | null
  retrieval_params: Record<string, any> | null
  retrieved_hits: Array<Record<string, any>>
  rerank_before: Array<Record<string, any>>
  rerank_after: Array<Record<string, any>>
  prompt_context: Array<Record<string, any>>
  prompt_text: string | null
  citations: Array<Record<string, any>>
  generation_stage: string | null
  error_message: string | null
  total_duration_ms: number | null
  rewrite_duration_ms: number | null
  embedding_duration_ms: number | null
  retrieval_duration_ms: number | null
  rerank_duration_ms: number | null
  prompt_build_duration_ms: number | null
  is_bad_case: boolean
  bad_case_category: string | null
  bad_case_note: string | null
  created_at: string
}

export interface RAGDebugLogListResponse {
  items: RAGDebugLogItem[]
  total: number
  limit: number
  offset: number
}

export const getRetrievalConfig = async (knowledgeBaseId: number, sessionId?: number | null) => {
  const { data } = await apiClient.get<RetrievalConfigResponse>('/rag-debug/config', {
    params: {
      knowledge_base_id: knowledgeBaseId,
      session_id: sessionId || undefined,
    },
  })
  return data
}

export const saveRetrievalConfig = async (knowledgeBaseId: number, payload: RetrievalConfigPayload, sessionId?: number | null) => {
  const { data } = await apiClient.put<RetrievalConfigResponse>('/rag-debug/config', payload, {
    params: {
      knowledge_base_id: knowledgeBaseId,
      session_id: sessionId || undefined,
    },
  })
  return data
}

export const listRagDebugLogs = async (params?: {
  knowledge_base_id?: number
  session_id?: number
  question?: string
  is_bad_case?: boolean
  bad_case_category?: string
  stage?: string
  start_at?: string
  end_at?: string
  limit?: number
  offset?: number
}) => {
  const { data } = await apiClient.get<RAGDebugLogListResponse>('/rag-debug/logs', { params })
  return data
}

export const markRagDebugBadCase = async (
  logId: number,
  payload: { is_bad_case: boolean; bad_case_category?: string | null; bad_case_note?: string | null },
) => {
  const { data } = await apiClient.patch<RAGDebugLogItem>(`/rag-debug/logs/${logId}/bad-case`, payload)
  return data
}

export const exportRagBadCases = async (knowledgeBaseId?: number) => {
  const { data } = await apiClient.get('/rag-debug/logs/export', {
    params: {
      knowledge_base_id: knowledgeBaseId || undefined,
    },
    responseType: 'blob',
  })
  return data as Blob
}
