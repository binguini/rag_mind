export type DocumentStatus = 'pending' | 'running' | 'completed' | 'failed' | 'deleting' | 'delete_failed' | 'deleted'

export interface DocumentItem {
  id: number
  knowledge_base_id: number
  filename: string
  file_type: string
  file_md5: string
  status: DocumentStatus
  task_id: string | null
  delete_task_id: string | null
  chunk_count: number
  error_message: string | null
  created_at: string
  page_count: number
  extracted_preview: string | null
  processing_started_at: string | null
  processing_finished_at: string | null
  retry_count: number
  processing_duration_ms: number | null
}

export interface DocumentChunkPreview {
  id: number
  chunk_index: number
  content: string
  source_page: number | null
  source_file: string
  created_at: string
}

export interface DocumentOperationLog {
  id: number
  operation_type: string
  status: string
  task_id: string | null
  stage: string | null
  elapsed_ms: number | null
  message: string | null
  created_at: string
}

export interface DocumentProgressMessage {
  document_id: number
  task_id: string | null
  status: DocumentStatus
  progress: number
  message: string
  stage?: string
}
