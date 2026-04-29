<template>
  <div style="max-width: 1180px; margin: 24px auto;">
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap;">
          <span>文档管理（M2）</span>
          <div style="display: flex; gap: 8px; flex-wrap: wrap;">
            <el-button size="small" @click="$router.push('/chat')">知识库对话</el-button>
            <el-button size="small" @click="$router.push('/knowledge-bases')">知识库管理</el-button>
            <el-button size="small" @click="$router.push('/settings/models')">模型设置</el-button>
            <el-button size="small" @click="$router.push('/settings/user')">用户设置</el-button>
          </div>
        </div>
      </template>

      <el-form :inline="true" :model="form">
        <el-form-item label="知识库">
          <el-select v-model="form.kbId" placeholder="选择知识库" style="width: 260px;">
            <el-option v-for="kb in knowledgeBases" :key="kb.id" :label="kb.name" :value="kb.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="文件">
          <el-upload
            accept=".txt,.pdf,.md,text/plain,text/markdown"
            :auto-upload="false"
            :limit="1"
            :on-change="onFileChange"
            :on-remove="onFileRemove"
            :show-file-list="true"
          >
            <el-button>选择文件</el-button>
          </el-upload>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :disabled="!selectedFile || uploading || !form.kbId" @click="handleUpload">
            {{ uploading ? '上传中...' : '上传文档' }}
          </el-button>
          <el-button @click="loadDocuments">刷新列表</el-button>
          <span style="margin-left: 8px; color: var(--el-text-color-secondary); font-size: 12px;">
            支持 txt / pdf / md
          </span>
          <span style="margin-left: 12px; color: var(--el-text-color-secondary); font-size: 12px;">
            提交成功后会自动刷新列表并同步任务进度
          </span>
        </el-form-item>
      </el-form>

      <el-alert
        v-if="uploadState.visible"
        :title="uploadState.title"
        :type="uploadState.type"
        :description="uploadState.message"
        :closable="true"
        show-icon
        style="margin-top: 16px;"
      >
        <template v-if="uploadState.detail" #default>
          <div style="margin-top: 6px; font-size: 12px; opacity: 0.9;">{{ uploadState.detail }}</div>
        </template>
      </el-alert>

      <TaskProgressPanel
        :visible="progress.visible"
        :title="progress.title"
        :task-id="progress.taskId"
        :progress="progress.percent"
        :status="progress.status"
        :message="progress.message"
        :stage-key="progress.stageKey"
        :stages="progress.stages"
        :success-statuses="progress.successStatuses"
        :failed-statuses="progress.failedStatuses"
        :status-label="progress.statusLabel"
        @close="progress.visible = false"
      />

      <div style="max-height: 420px; overflow-y: auto; margin-top: 16px; border: 1px solid var(--el-border-color-lighter); border-radius: 8px;">
        <el-table :data="documents" :row-class-name="tableRowClassName" style="width: 100%;">
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column prop="filename" label="文件名" min-width="220" />
          <el-table-column prop="file_type" label="类型" width="100" />
          <el-table-column label="状态" width="140">
            <template #default="scope">
              <el-tooltip
                v-if="(scope.row.status === 'failed' || scope.row.status === 'delete_failed') && scope.row.error_message"
                :content="scope.row.error_message"
                placement="top"
              >
                <el-tag :type="statusTagType(scope.row.status)" effect="light">
                  {{ statusLabel(scope.row.status) }}
                </el-tag>
              </el-tooltip>
              <el-tag v-else :type="statusTagType(scope.row.status)" effect="light">
                {{ statusLabel(scope.row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="chunk_count" label="块数" width="100" />
          <el-table-column prop="created_at" label="创建时间" width="220" />
          <el-table-column label="操作" min-width="320">
            <template #default="scope">
              <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                <el-button size="small" @click="openDetail(scope.row.id)">详情</el-button>
                <el-button
                  v-if="scope.row.status === 'failed'"
                  size="small"
                  type="warning"
                  plain
                  @click="handleRetry(scope.row.id)"
                >
                  重试
                </el-button>
                <el-button
                  v-if="scope.row.status === 'delete_failed'"
                  size="small"
                  type="warning"
                  plain
                  @click="handleDelete(scope.row.id)"
                >
                  重试删除
                </el-button>
                <el-button
                  size="small"
                  type="danger"
                  plain
                  :disabled="scope.row.status === 'completed' || scope.row.status === 'failed' || scope.row.status === 'deleting' || scope.row.status === 'delete_failed' || scope.row.status === 'deleted'"
                  @click="cancel(scope.row.id)"
                >
                  取消
                </el-button>
                <el-button
                  size="small"
                  type="danger"
                  plain
                  :disabled="scope.row.status === 'running' || scope.row.status === 'deleting'"
                  @click="handleDelete(scope.row.id)"
                >
                  删除
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>

    <el-drawer v-model="detailDrawer.visible" title="文档详情" size="55%" destroy-on-close>
      <template v-if="detailDrawer.loading">
        <div style="padding: 24px; display: flex; justify-content: center;">
          <el-skeleton :rows="8" animated style="width: 100%;" />
        </div>
      </template>
      <template v-else-if="detailDrawer.document">
        <div style="display: flex; flex-direction: column; gap: 16px;">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="文档 ID">{{ detailDrawer.document.id }}</el-descriptions-item>
            <el-descriptions-item label="文件名">{{ detailDrawer.document.filename }}</el-descriptions-item>
            <el-descriptions-item label="文件类型">{{ detailDrawer.document.file_type }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="statusTagType(detailDrawer.document.status)" effect="light">
                {{ statusLabel(detailDrawer.document.status) }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ formatDate(detailDrawer.document.created_at) }}</el-descriptions-item>
            <el-descriptions-item label="任务 ID">{{ detailDrawer.document.task_id || '-' }}</el-descriptions-item>
            <el-descriptions-item label="删除任务 ID">{{ detailDrawer.document.delete_task_id || '-' }}</el-descriptions-item>
            <el-descriptions-item label="页数">{{ detailDrawer.document.page_count }}</el-descriptions-item>
            <el-descriptions-item label="Chunk 数">{{ detailDrawer.document.chunk_count }}</el-descriptions-item>
            <el-descriptions-item label="重试次数">{{ detailDrawer.document.retry_count }}</el-descriptions-item>
            <el-descriptions-item label="处理耗时">{{ formatDuration(detailDrawer.document.processing_duration_ms) }}</el-descriptions-item>
            <el-descriptions-item label="开始时间">{{ formatDate(detailDrawer.document.processing_started_at) }}</el-descriptions-item>
            <el-descriptions-item label="结束时间">{{ formatDate(detailDrawer.document.processing_finished_at) }}</el-descriptions-item>
          </el-descriptions>

          <el-card shadow="never">
            <template #header>
              <div style="font-weight: 600;">提取结果预览</div>
            </template>
            <div class="preview-content">{{ detailDrawer.document.extracted_preview || '暂无提取结果预览' }}</div>
          </el-card>

          <el-alert
            v-if="detailDrawer.document.error_message"
            title="失败原因"
            type="error"
            :description="detailDrawer.document.error_message"
            show-icon
            :closable="false"
          />

          <el-card shadow="never">
            <template #header>
              <div style="font-weight: 600;">操作与处理日志</div>
            </template>
            <el-empty v-if="!detailDrawer.logs.length" description="暂无操作日志" />
            <div v-else style="display: flex; flex-direction: column; gap: 10px;">
              <div v-for="log in detailDrawer.logs" :key="log.id" class="log-card">
                <div class="log-card__header">
                  <span>{{ operationTypeLabel(log.operation_type) }}</span>
                  <span>{{ formatDate(log.created_at) }}</span>
                </div>
                <div class="log-card__meta">
                  <span>状态：{{ log.status }}</span>
                  <span>阶段：{{ log.stage || '-' }}</span>
                  <span>耗时：{{ formatDuration(log.elapsed_ms) }}</span>
                  <span>任务：{{ log.task_id || '-' }}</span>
                </div>
                <div class="log-card__body">{{ log.message || '-' }}</div>
              </div>
            </div>
          </el-card>

          <el-card shadow="never">
            <template #header>
              <div style="font-weight: 600;">Chunk 预览</div>
            </template>
            <el-empty v-if="!detailDrawer.chunks.length" description="暂无 chunk 数据" />
            <div v-else style="display: flex; flex-direction: column; gap: 12px;">
              <div v-for="chunk in detailDrawer.chunks" :key="chunk.id" class="chunk-card">
                <div class="chunk-card__header">
                  <span>Chunk #{{ chunk.chunk_index }}</span>
                  <span>页码：{{ chunk.source_page ?? '-' }}</span>
                </div>
                <div class="chunk-card__body">{{ chunk.content }}</div>
              </div>
            </div>
          </el-card>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { apiClient } from '../api/client'
import {
  cancelDocument,
  deleteDocument,
  getDocument,
  listDocumentChunks,
  listDocumentLogs,
  listDocuments,
  retryDocument,
  uploadDocument,
} from '../api/documents'
import TaskProgressPanel from '../components/TaskProgressPanel.vue'
import type {
  DocumentChunkPreview,
  DocumentItem,
  DocumentOperationLog,
  DocumentProgressMessage,
  DocumentStatus,
} from '../types/document'

const form = reactive({ kbId: 0 })
const knowledgeBases = ref<any[]>([])
const selectedFile = ref<File | null>(null)
const uploading = ref(false)
const documents = ref<DocumentItem[]>([])
const uploadState = reactive({
  visible: false,
  title: '',
  type: 'info' as 'success' | 'info' | 'warning' | 'error',
  message: '',
  detail: '',
})
const progress = reactive({
  visible: false,
  title: '任务进度',
  taskId: '',
  percent: 0,
  status: 'pending' as DocumentStatus | string,
  stageKey: '',
  stages: [] as Array<{ key: string; label: string }>,
  successStatuses: ['completed'] as string[],
  failedStatuses: ['failed'] as string[],
  statusLabel: '',
  message: '',
})
const detailDrawer = reactive<{
  visible: boolean
  loading: boolean
  document: DocumentItem | null
  chunks: DocumentChunkPreview[]
  logs: DocumentOperationLog[]
}>({
  visible: false,
  loading: false,
  document: null,
  chunks: [],
  logs: [],
})
const recentlyUploadedIds = ref<number[]>([])
let ws: WebSocket | null = null

const statusLabel = (status: DocumentStatus) => {
  const map: Record<DocumentStatus, string> = {
    pending: '等待中',
    running: '处理中',
    completed: '已完成',
    failed: '已失败',
    deleting: '删除中',
    delete_failed: '删除失败',
    deleted: '已删除',
  }
  return map[status]
}

const operationTypeLabel = (operationType: string) => {
  const map: Record<string, string> = {
    retry_requested: '发起重试',
    retry_succeeded: '重试成功',
    retry_failed: '重试失败',
    delete_requested: '发起删除',
    delete_succeeded: '删除成功',
    delete_failed: '删除失败',
    process_started: '处理开始',
    process_completed: '处理完成',
    process_failed: '处理失败',
    parse_started: '解析开始',
    parse_completed: '解析完成',
    chunking_started: '切分开始',
    chunking_completed: '切分完成',
    embedding_started: '向量生成开始',
    embedding_completed: '向量生成完成',
    vector_store_started: '入库开始',
    vector_store_completed: '入库完成',
  }
  return map[operationType] || operationType
}

const stageLabel = (stage?: string) => {
  const map: Record<string, string> = {
    parsing: '解析中',
    chunking: '切分中',
    embedding: '向量化中',
    vector_store: '入库中',
    completed: '已完成',
    processing: '处理中',
    deleting: '删除中',
    delete_completed: '删除完成',
  }
  return map[stage || 'processing'] || '处理中'
}

const buildProgressFlow = (kind: 'upload' | 'delete' | 'retry') => {
  if (kind === 'delete') {
    return {
      stages: [
        { key: 'deleting', label: '清理中' },
        { key: 'delete_completed', label: '已完成' },
      ],
      successStatuses: ['deleted'],
      failedStatuses: ['delete_failed'],
      terminalStageKey: 'delete_completed',
    }
  }

  return {
    stages: [
      { key: 'parsing', label: '解析中' },
      { key: 'chunking', label: '切分中' },
      { key: 'embedding', label: '向量化中' },
      { key: 'vector_store', label: '入库中' },
      { key: 'completed', label: '已完成' },
    ],
    successStatuses: ['completed'],
    failedStatuses: ['failed'],
    terminalStageKey: 'completed',
  }
}

const statusTagType = (status: DocumentStatus) => {
  const map: Record<DocumentStatus, 'info' | 'warning' | 'success' | 'danger'> = {
    pending: 'info',
    running: 'warning',
    completed: 'success',
    failed: 'danger',
    deleting: 'warning',
    delete_failed: 'danger',
    deleted: 'info',
  }
  return map[status]
}

const formatDate = (value?: string | null) => {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN')
}

const formatDuration = (durationMs: number | null) => {
  if (durationMs == null) return '-'
  if (durationMs < 1000) return `${durationMs} ms`
  return `${(durationMs / 1000).toFixed(2)} s`
}

const syncProgressPanel = (
  payload: DocumentProgressMessage,
  fallbackTaskId: string,
  title = '任务进度',
  flowKind: 'upload' | 'delete' | 'retry' = 'upload',
) => {
  const flow = buildProgressFlow(flowKind)
  progress.visible = true
  progress.title = title
  progress.taskId = payload.task_id || fallbackTaskId
  progress.percent = payload.progress
  progress.status = payload.status
  progress.stageKey = payload.status === 'deleted' ? flow.terminalStageKey : payload.stage || ''
  progress.stages = flow.stages
  progress.successStatuses = flow.successStatuses
  progress.failedStatuses = flow.failedStatuses
  progress.statusLabel = payload.status
  progress.message = payload.status === 'deleted' ? '删除任务已完成，文档数据已清理' : payload.message || stageLabel(payload.stage)
}

const loadKnowledgeBases = async () => {
  try {
    const { data } = await apiClient.get('/knowledge-bases')
    knowledgeBases.value = data
    if (!form.kbId && data.length > 0) {
      form.kbId = data[0].id
    }
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '加载知识库失败')
  }
}

const onFileChange = (file: any) => {
  selectedFile.value = file.raw as File
}

const onFileRemove = () => {
  selectedFile.value = null
}

const connectProgress = (taskId: string) => {
  if (ws) {
    ws.close()
  }
  const base = import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8000'
  ws = new WebSocket(`${base}/ws/tasks/${taskId}`)
  ws.onmessage = (event) => {
    const payload = JSON.parse(event.data) as DocumentProgressMessage
    syncProgressPanel(payload, taskId, '上传任务进度', 'upload')
    if (payload.document_id) {
      recentlyUploadedIds.value = Array.from(new Set([payload.document_id, ...recentlyUploadedIds.value])).slice(0, 10)
    }
    loadDocuments()
    if (detailDrawer.visible && detailDrawer.document?.id === payload.document_id) {
      openDetail(payload.document_id)
    }
  }
  ws.onerror = () => {
    loadDocuments()
  }
}

const loadDocuments = async () => {
  if (!form.kbId) return
  try {
    const data = await listDocuments(form.kbId)
    documents.value = data
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '加载文档失败')
  }
}

const isRecentlyUploaded = (documentId: number) => recentlyUploadedIds.value.includes(documentId)

const tableRowClassName = ({ row }: { row: DocumentItem }) =>
  isRecentlyUploaded(row.id) ? 'recent-upload-row' : ''

const openDetail = async (documentId: number) => {
  detailDrawer.visible = true
  detailDrawer.loading = true
  try {
    const [document, chunks, logs] = await Promise.all([
      getDocument(documentId),
      listDocumentChunks(documentId),
      listDocumentLogs(documentId),
    ])
    detailDrawer.document = document
    detailDrawer.chunks = chunks
    detailDrawer.logs = logs
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '加载文档详情失败')
    detailDrawer.visible = false
  } finally {
    detailDrawer.loading = false
  }
}

const handleUpload = async () => {
  if (!selectedFile.value) {
    ElMessage.warning('请选择文件')
    return
  }
  if (!form.kbId) {
    ElMessage.warning('请选择知识库')
    return
  }
  uploading.value = true
  uploadState.visible = true
  uploadState.title = '正在提交上传'
  uploadState.type = 'info'
  uploadState.message = `文件「${selectedFile.value.name}」正在上传并进入后台处理流程。`
  uploadState.detail = ''
  try {
    const result = await uploadDocument(form.kbId, selectedFile.value)
    ElMessage.success('上传已提交')
    progress.visible = true
    const flow = buildProgressFlow('upload')
    progress.title = '上传任务进度'
    progress.taskId = result.task_id || ''
    progress.percent = result.status === 'completed' ? 100 : 5
    progress.status = result.status
    progress.stageKey = result.status === 'completed' ? flow.terminalStageKey : 'parsing'
    progress.stages = flow.stages
    progress.successStatuses = flow.successStatuses
    progress.failedStatuses = flow.failedStatuses
    progress.statusLabel = result.status
    progress.message = result.status === 'failed' ? '任务未成功，请查看失败原因' : '任务已提交，等待处理'

    uploadState.title = result.status === 'completed' ? '文档已完成' : '文档已提交后台处理'
    uploadState.type = result.status === 'failed' ? 'error' : result.status === 'completed' ? 'success' : 'info'
    uploadState.message =
      result.status === 'completed'
        ? '文档已完成入库，可立即在列表中查看。'
        : '文档已成功提交，正在后台执行解析、切分和向量化。'
    uploadState.detail = result.task_id ? `任务ID：${result.task_id}` : `文档ID：${result.id}`

    if (result.task_id) {
      connectProgress(result.task_id)
    }
    await loadDocuments()
  } catch (error: any) {
    uploadState.visible = true
    uploadState.title = '上传失败'
    uploadState.type = 'error'
    uploadState.message = error?.response?.data?.detail || '上传失败'
    uploadState.detail = ''
    ElMessage.error(error?.response?.data?.detail || '上传失败')
  } finally {
    uploading.value = false
  }
}

const cancel = async (documentId: number) => {
  try {
    const doc = await cancelDocument(documentId)
    ElMessage.success(`已取消：${doc.filename}`)
    await loadDocuments()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '取消失败')
  }
}

const handleRetry = async (documentId: number) => {
  try {
    const doc = await retryDocument(documentId)
    ElMessage.success(`已重新提交：${doc.filename}`)
    if (doc.task_id) {
      connectProgress(doc.task_id)
      const flow = buildProgressFlow('retry')
      syncProgressPanel(
        {
          task_id: doc.task_id,
          document_id: doc.id,
          status: doc.status,
          progress: 5,
          message: '重试任务已提交，等待后台处理',
          stage: 'processing',
        },
        doc.task_id,
        '重试任务进度',
        'retry',
      )
      progress.stages = flow.stages
      progress.successStatuses = flow.successStatuses
      progress.failedStatuses = flow.failedStatuses
    }
    await loadDocuments()
    if (detailDrawer.visible) {
      await openDetail(documentId)
    }
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '重试失败')
  }
}

const handleDelete = async (documentId: number) => {
  try {
    await ElMessageBox.confirm('删除任务将异步执行，并清理该文档的 chunk 与向量数据，是否继续？', '删除文档', {
      type: 'warning',
      confirmButtonText: '确认删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }

  try {
    const doc = await deleteDocument(documentId)
    ElMessage.success(doc.status === 'deleting' ? `已提交删除任务：${doc.filename}` : `已删除：${doc.filename}`)
    if (doc.delete_task_id) {
      connectProgress(doc.delete_task_id)
      syncProgressPanel(
        {
          task_id: doc.delete_task_id,
          document_id: doc.id,
          status: doc.status,
          progress: 5,
          message: '删除任务已提交，等待后台清理',
          stage: 'deleting',
        },
        doc.delete_task_id,
        '删除任务进度',
        'delete',
      )
    }
    await loadDocuments()
    if (detailDrawer.visible) {
      await openDetail(documentId)
    }
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '删除失败')
  }
}

watch(
  () => form.kbId,
  async (value, oldValue) => {
    if (value && value !== oldValue) {
      await loadDocuments()
    }
  },
)

onMounted(async () => {
  await loadKnowledgeBases()
  await loadDocuments()
})
onBeforeUnmount(() => {
  if (ws) ws.close()
})
</script>

<style scoped>
:deep(.recent-upload-row) {
  animation: recent-upload-highlight 2.6s ease-out 1;
  background: rgba(103, 194, 58, 0.08);
}

.preview-content {
  line-height: 1.7;
  white-space: pre-wrap;
  color: var(--el-text-color-primary);
}

.chunk-card,
.log-card {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  padding: 12px 14px;
  background: var(--el-fill-color-blank);
}

.chunk-card__header,
.log-card__header,
.log-card__meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  flex-wrap: wrap;
}

.chunk-card__body,
.log-card__body {
  white-space: pre-wrap;
  line-height: 1.65;
  color: var(--el-text-color-primary);
}

@keyframes recent-upload-highlight {
  0% {
    background: rgba(103, 194, 58, 0.22);
  }
  100% {
    background: rgba(103, 194, 58, 0.08);
  }
}
</style>
