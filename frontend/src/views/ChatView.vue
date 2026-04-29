<template>
  <div class="chat-page">
    <el-card class="chat-layout">
      <template #header>
        <div class="chat-header">
          <div>
            <div style="font-size: 18px; font-weight: 700;">知识库对话</div>
            <div style="font-size: 12px; color: #6b7280; margin-top: 4px;">当前知识库：{{ currentKnowledgeBaseName }}</div>
          </div>
          <div class="chat-shortcuts">
            <el-tag effect="plain">{{ currentUserLabel }}</el-tag>
            <el-button size="small" @click="$router.push('/knowledge-bases')">知识库管理</el-button>
            <el-button size="small" @click="$router.push('/documents')">文档管理</el-button>
            <el-button size="small" @click="$router.push('/settings/models')">模型设置</el-button>
          </div>
        </div>
      </template>

      <div class="chat-shell">
        <aside class="session-panel">
          <el-form label-position="top">
            <el-form-item label="知识库">
              <el-select v-model="kbId" placeholder="选择知识库" style="width: 100%;" @change="handleKnowledgeBaseChange">
                <el-option v-for="kb in knowledgeBases" :key="kb.id" :label="kb.name" :value="kb.id" />
              </el-select>
            </el-form-item>
          </el-form>

          <div class="panel-toolbar">
            <el-button type="primary" plain :disabled="!kbId" @click="createSession">新建会话</el-button>
            <el-button :disabled="!currentSessionId" @click="renameSession">重命名</el-button>
            <el-button :disabled="!kbId" @click="loadSessions">刷新</el-button>
          </div>

          <div class="session-list">
            <div
              v-for="session in sessions"
              :key="session.id"
              class="session-item"
              :class="{ active: session.id === currentSessionId }"
              @click="selectSession(session.id)"
            >
              <div class="session-title">{{ session.title }}</div>
              <div class="session-meta">{{ formatTime(session.last_message_at) }}</div>
            </div>
          </div>
        </aside>

        <section class="chat-main">
          <el-card v-if="streaming" class="stream-card" shadow="never">
            <template #header>生成中</template>
            <el-progress :percentage="streamProgress" :status="streamStatus" />
          </el-card>

          <div class="message-panel">
            <div
              v-for="msg in messages"
              :key="msg.id"
              class="message-item"
              :class="msg.role"
            >
              <div class="message-head">
                <strong>{{ msg.role === 'user' ? '用户' : '助手' }}</strong>
              </div>
              <div class="message-content">
                <div v-if="msg.role === 'user'" class="user-content">{{ msg.content }}</div>
                <MarkdownMessage v-else :content="msg.content" />
              </div>
            </div>
          </div>

          <div class="composer-panel">
            <el-input
              v-model="question"
              type="textarea"
              :rows="4"
              placeholder="请输入问题，例如：这份文档的核心结论是什么？"
            />

            <div class="action-row">
              <el-button type="primary" :disabled="!currentSessionId || !question.trim() || streaming" @click="sendQuestion">
                {{ streaming ? '生成中...' : '发送' }}
              </el-button>
              <el-button :disabled="!streaming" @click="stopStream">停止生成</el-button>
              <el-button :disabled="!lastQuestion || streaming" @click="retryLast">重新生成</el-button>
              <el-button @click="copyAnswer" :disabled="!assistantAnswer">复制答案</el-button>
              <el-button :disabled="!currentSessionId" @click="removeSession">删除当前会话</el-button>
            </div>
          </div>

          <el-card v-if="citations.length" class="citation-card" shadow="never">
            <template #header>引用来源</template>
            <el-timeline>
              <el-timeline-item v-for="item in citations" :key="item.chunk_id" :timestamp="`score: ${Number(item.score || 0).toFixed(3)}`">
                <div><strong>{{ item.document_name }}</strong> / chunk {{ item.chunk_index }} / page {{ item.page ?? '-' }}</div>
                <div class="citation-content">{{ item.content }}</div>
              </el-timeline-item>
            </el-timeline>
          </el-card>
        </section>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import MarkdownMessage from '../components/MarkdownMessage.vue'
import { apiClient } from '../api/client'
import {
  createChatSession,
  createStreamRequest,
  deleteChatSession,
  listChatMessages,
  listChatSessions,
  type ChatMessageItem,
  type ChatSessionItem,
  updateChatSession,
} from '../api/chat'
import { getCurrentUserLabel } from '../utils/auth'

const knowledgeBases = ref<any[]>([])
const sessions = ref<ChatSessionItem[]>([])
const currentSessionId = ref<number | null>(null)
const kbId = ref<number | null>(null)
const question = ref('')
const assistantAnswer = ref('')
const lastQuestion = ref('')
const streaming = ref(false)
const streamProgress = ref(0)
const streamStatus = ref<'success' | 'exception' | undefined>(undefined)
const citations = ref<Array<Record<string, any>>>([])
const messages = ref<ChatMessageItem[]>([])
let abortController: AbortController | null = null

const currentUserLabel = computed(() => getCurrentUserLabel())
const currentKnowledgeBaseName = computed(() => knowledgeBases.value.find((item) => item.id === kbId.value)?.name || '未选择')

const loadKnowledgeBases = async () => {
  const { data } = await apiClient.get('/knowledge-bases')
  knowledgeBases.value = data
  if (!kbId.value && data.length > 0) kbId.value = data[0].id
}

const loadSessions = async () => {
  if (!kbId.value) {
    sessions.value = []
    currentSessionId.value = null
    messages.value = []
    return
  }
  sessions.value = await listChatSessions({ mode: 'rag', knowledge_base_id: kbId.value })
  if (sessions.value.length) {
    if (!currentSessionId.value || !sessions.value.some((item) => item.id === currentSessionId.value)) {
      await selectSession(sessions.value[0].id)
    }
  } else {
    currentSessionId.value = null
    messages.value = []
  }
}

const createSession = async () => {
  if (!kbId.value) return
  const session = await createChatSession({ mode: 'rag', knowledge_base_id: kbId.value })
  sessions.value.unshift(session)
  await selectSession(session.id)
}

const selectSession = async (sessionId: number) => {
  currentSessionId.value = sessionId
  messages.value = await listChatMessages(sessionId)
  const lastAssistant = [...messages.value].reverse().find((item) => item.role === 'assistant')
  assistantAnswer.value = lastAssistant?.content || ''
  citations.value = lastAssistant?.citations || []
}

const sendQuestion = async () => {
  if (!currentSessionId.value || !question.value.trim()) return
  streaming.value = true
  streamProgress.value = 0
  streamStatus.value = undefined
  assistantAnswer.value = ''
  citations.value = []
  lastQuestion.value = question.value

  abortController = new AbortController()
  try {
    const response = await createStreamRequest(currentSessionId.value, { message: question.value }, abortController.signal)
    const reader = response.body?.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let assistantMessageId: number | null = null
    let localMessages = [...messages.value]
    if (!reader) throw new Error('无法建立流式连接')

    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() || ''
      for (const part of parts) {
        const dataLine = part.split('\n').find((line) => line.startsWith('data: '))
        if (!dataLine) continue
        const payload = JSON.parse(dataLine.slice(6))
        if (payload.type === 'message_start') {
          assistantMessageId = payload.message_id
          localMessages = await listChatMessages(currentSessionId.value)
          messages.value = localMessages
        } else if (payload.type === 'delta' && assistantMessageId) {
          assistantAnswer.value += payload.content || ''
          const target = localMessages.find((item) => item.id === assistantMessageId)
          if (target) {
            target.content = assistantAnswer.value
            messages.value = [...localMessages]
          }
          streamProgress.value = Math.min(95, streamProgress.value + 1)
        } else if (payload.type === 'message_end') {
          assistantAnswer.value = payload.answer || assistantAnswer.value
          citations.value = payload.citations || []
          messages.value = await listChatMessages(currentSessionId.value)
          sessions.value = await listChatSessions({ mode: 'rag', knowledge_base_id: kbId.value || undefined })
          streamProgress.value = 100
          streamStatus.value = 'success'
        } else if (payload.type === 'error') {
          throw new Error(payload.error || '生成失败')
        }
      }
    }
    question.value = ''
  } catch (error: any) {
    if (error?.name !== 'AbortError') {
      streamStatus.value = 'exception'
      ElMessage.error(error?.message || '生成失败')
    }
  } finally {
    streaming.value = false
  }
}

const stopStream = () => {
  abortController?.abort()
  streaming.value = false
  streamStatus.value = 'exception'
}

const retryLast = async () => {
  question.value = lastQuestion.value
  await sendQuestion()
}

const copyAnswer = async () => {
  await navigator.clipboard.writeText(assistantAnswer.value)
  ElMessage.success('已复制答案')
}

const renameSession = async () => {
  if (!currentSessionId.value) return
  const current = sessions.value.find((item) => item.id === currentSessionId.value)
  const { value } = await ElMessageBox.prompt('请输入新的会话名称', '重命名会话', {
    inputValue: current?.title || '',
    inputPattern: /\S+/,
    inputErrorMessage: '名称不能为空',
  })
  await updateChatSession(currentSessionId.value, { title: value })
  await loadSessions()
}

const removeSession = async () => {
  if (!currentSessionId.value) return
  await ElMessageBox.confirm('确认删除当前会话？', '提示', { type: 'warning' })
  await deleteChatSession(currentSessionId.value)
  currentSessionId.value = null
  messages.value = []
  assistantAnswer.value = ''
  citations.value = []
  await loadSessions()
  if (!sessions.value.length && kbId.value) {
    await createSession()
  }
}

const handleKnowledgeBaseChange = async () => {
  currentSessionId.value = null
  messages.value = []
  citations.value = []
  assistantAnswer.value = ''
  await loadSessions()
  if (!sessions.value.length && kbId.value) {
    await createSession()
  }
}

const formatTime = (value: string) => new Date(value).toLocaleString()

onMounted(async () => {
  await loadKnowledgeBases()
  await loadSessions()
  if (!sessions.value.length && kbId.value) {
    await createSession()
  }
})
</script>

<style scoped>
.chat-page {
  max-width: 1280px;
  margin: 24px auto;
}
.chat-layout {
  width: 100%;
}
.chat-shell {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 16px;
  min-height: 680px;
}
.session-panel {
  border-right: 1px solid #ebeef5;
  padding-right: 16px;
}
.panel-toolbar {
  margin-bottom: 12px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.session-list {
  display: grid;
  gap: 8px;
}
.session-item {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 10px 12px;
  cursor: pointer;
  background: #fff;
}
.session-item.active {
  border-color: #409eff;
  background: #ecf5ff;
}
.session-title {
  font-weight: 600;
}
.session-meta {
  margin-top: 6px;
  font-size: 12px;
  color: #6b7280;
}
.message-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.chat-main {
  min-width: 0;
  display: grid;
  gap: 16px;
}
.stream-card {
  margin: 0;
}
.message-panel {
  display: grid;
  gap: 12px;
}
.message-item {
  padding: 10px 14px;
  border-radius: 12px;
}
.message-item.user {
  background: #ecf5ff;
}
.message-item.assistant {
  background: #f5f7fa;
}
.message-content {
  margin-top: 4px;
}
.user-content {
  white-space: pre-wrap;
  line-height: 1.4;
}
.composer-panel {
  display: grid;
  gap: 12px;
}
.action-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.citation-card {
  margin-top: 0;
}
.citation-content {
  white-space: pre-wrap;
  color: #606266;
  line-height: 1.35;
}
.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.chat-shortcuts {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}
</style>
