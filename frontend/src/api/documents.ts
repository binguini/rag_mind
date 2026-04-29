import { apiClient } from './client'
import type { DocumentChunkPreview, DocumentItem, DocumentOperationLog } from '../types/document'

export const uploadDocument = async (kbId: number, file: File): Promise<DocumentItem> => {
  const form = new FormData()
  form.append('kb_id', String(kbId))
  form.append('file', file)
  const { data } = await apiClient.post('/documents/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export const listDocuments = async (kbId: number): Promise<DocumentItem[]> => {
  const { data } = await apiClient.get('/documents', { params: { kb_id: kbId } })
  return data
}

export const getDocument = async (documentId: number): Promise<DocumentItem> => {
  const { data } = await apiClient.get(`/documents/${documentId}`)
  return data
}

export const listDocumentChunks = async (documentId: number, limit = 20): Promise<DocumentChunkPreview[]> => {
  const { data } = await apiClient.get(`/documents/${documentId}/chunks`, { params: { limit } })
  return data
}

export const listDocumentLogs = async (documentId: number, limit = 20): Promise<DocumentOperationLog[]> => {
  const { data } = await apiClient.get(`/documents/${documentId}/logs`, { params: { limit } })
  return data
}

export const cancelDocument = async (documentId: number): Promise<DocumentItem> => {
  const { data } = await apiClient.post(`/documents/${documentId}/cancel`)
  return data
}

export const retryDocument = async (documentId: number): Promise<DocumentItem> => {
  const { data } = await apiClient.post(`/documents/${documentId}/retry`)
  return data
}

export const deleteDocument = async (documentId: number, deleteSourceFile = false): Promise<DocumentItem> => {
  const { data } = await apiClient.delete(`/documents/${documentId}`, {
    params: { delete_source_file: deleteSourceFile },
  })
  return data
}
