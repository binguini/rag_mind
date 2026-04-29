import { apiClient } from './client'

export type ChatMode = 'general' | 'rag'
export type ChatSessionStatus = 'active' | 'archived' | 'deleted'
export type ChatRole = 'system' | 'user' | 'assistant' | 'tool'
export type ChatMessageStatus = 'streaming' | 'done' | 'failed' | 'cancelled'

export interface ChatSessionItem {
  id: number
  mode: ChatMode
  knowledge_base_id: number | null
  title: string
  summary: string | null
  status: ChatSessionStatus
  message_count: number
  last_message_at: string
  created_at: string
  updated_at: string
}

export interface ChatMessageItem {
  id: number
  session_id: number
  role: ChatRole
  content: string
  content_type: string
  status: ChatMessageStatus
  citations: Array<Record<string, any>>
  meta: Record<string, any> | null
  error_message: string | null
  parent_message_id: number | null
  created_at: string
  updated_at: string
}

export interface CreateChatSessionPayload {
  mode: ChatMode
  knowledge_base_id?: number
  title?: string
}

export interface UpdateChatSessionPayload {
  title?: string
  status?: ChatSessionStatus
}

export interface StreamChatPayload {
  message: string
}

export const listChatSessions = async (params?: {
  mode?: ChatMode
  knowledge_base_id?: number
  status?: ChatSessionStatus
}) => {
  const { data } = await apiClient.get<ChatSessionItem[]>('/chat/sessions', { params })
  return data
}

export const createChatSession = async (payload: CreateChatSessionPayload) => {
  const { data } = await apiClient.post<ChatSessionItem>('/chat/sessions', payload)
  return data
}

export const updateChatSession = async (sessionId: number, payload: UpdateChatSessionPayload) => {
  const { data } = await apiClient.patch<ChatSessionItem>(`/chat/sessions/${sessionId}`, payload)
  return data
}

export const deleteChatSession = async (sessionId: number) => {
  const { data } = await apiClient.delete<{ ok: boolean }>(`/chat/sessions/${sessionId}`)
  return data
}

export const listChatMessages = async (sessionId: number) => {
  const { data } = await apiClient.get<ChatMessageItem[]>(`/chat/sessions/${sessionId}/messages`)
  return data
}

export const createStreamRequest = async (sessionId: number, payload: StreamChatPayload, signal?: AbortSignal) => {
  const token = localStorage.getItem('access_token') || ''
  return fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'}/chat/sessions/${sessionId}/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
    signal,
  })
}
