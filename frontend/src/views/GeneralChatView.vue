<template>
  <div class="chat-page">
    <el-card class="chat-layout">
      <template #header>
        <div class="chat-header">
          <div>
            <div style="font-size: 18px; font-weight: 700;">通用对话</div>
            <div style="font-size: 12px; color: #6b7280; margin-top: 4px;">统一会话架构，支持多轮对话与历史恢复</div>
          </div>
          <div class="chat-shortcuts">
            <el-tag effect="plain">{{ currentUserLabel }}</el-tag>
            <el-button size="small" @click="$router.push('/chat')">知识库对话</el-button>
            <el-button size="small" @click="$router.push('/knowledge-bases')">知识库管理</el-button>
            <el-button size="small" @click="$router.push('/documents')">文档管理</el-button>
            <el-button size="small" @click="$router.push('/settings/models')">模型设置</el-button>
          </div>
        </div>
      </template>

      <div class="chat-shell">
        <aside class="session-panel">
          <div class="panel-toolbar">
            <el-button type="primary" plain @click="createSession">新建对话</el-button>
            <el-button :disabled="!currentSessionId" @click="renameSession">重命名</el-button>
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
          <div ref="messageListRef" class="message-list">
            <div v-if="!messages.length" class="empty-state">
              <div class="empty-state__title">开始一段新的对话</div>
              <div class="empty-state__desc">支持多轮追问、流式输出与历史会话恢复。</div>
            </div>

            <div
              v-for="msg in messages"
              :key="msg.id"
              class="message-row"
              :class="msg.role === 'user' ? 'message-row--user' : 'message-row--assistant'"
            >
              <div class="message-avatar">{{ msg.role === 'user' ? '问' : '答' }}</div>
              <div class="message-bubble" :class="msg.role === 'user' ? 'message-bubble--user' : 'message-bubble--assistant'">
                <div class="message-head">
                  <strong>{{ msg.role === 'user' ? '你' : '助手' }}</strong>
                  <span class="message-role-tip">{{ msg.role === 'user' ? '已发送' : streaming && isLatestAssistantMessage(msg.id) ? '正在生成…' : '已回复' }}</span>
                </div>
                <div class="message-content">
                  <div v-if="msg.role === 'user'" class="message-text">{{ msg.content }}</div>
                  <MarkdownMessage v-else :content="msg.content" />
                </div>
              </div>
            </div>
          </div>

          <div class="composer-card">
            <div class="composer-head">
              <div>
                <div class="composer-title">继续提问</div>
                <div class="composer-subtitle">Shift + Enter 换行，Enter 可直接发送</div>
              </div>
              <el-button text :disabled="!currentSessionId" @click="removeSession">删除当前会话</el-button>
            </div>

            <el-input
              v-model="question"
              class="composer-input"
              type="textarea"
              :rows="4"
              resize="none"
              placeholder="请输入任意问题，例如：帮我总结一下今天的工作安排。"
              @keydown="handleInputKeydown"
            />

            <div class="composer-footer">
              <div class="composer-actions">
                <el-button type="primary" :disabled="!currentSessionId || !question.trim() || streaming" @click="sendQuestion">
                  {{ streaming ? '生成中...' : '发送' }}
                </el-button>
                <el-button :disabled="!streaming" @click="stopStream">停止生成</el-button>
                <el-button :disabled="!lastQuestion || streaming" @click="retryLast">重新生成</el-button>
                <el-button @click="copyAnswer" :disabled="!assistantAnswer">复制答案</el-button>
              </div>
              <div class="composer-meta">
                <span>{{ question.trim().length }} 字</span>
                <span v-if="streaming" class="stream-indicator">回答生成中</span>
              </div>
            </div>
          </div>
        </section>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import MarkdownMessage from '../components/MarkdownMessage.vue'
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

const currentUserLabel = computed(() => getCurrentUserLabel())
const sessions = ref<ChatSessionItem[]>([])
const currentSessionId = ref<number | null>(null)
const question = ref('')
const assistantAnswer = ref('')
const lastQuestion = ref('')
const streaming = ref(false)
const messages = ref<ChatMessageItem[]>([])
const messageListRef = ref<HTMLElement | null>(null)
let abortController: AbortController | null = null

const scrollToBottom = async (smooth = false) => {
  await nextTick()
  const el = messageListRef.value
  if (!el) return
  el.scrollTo({ top: el.scrollHeight, behavior: smooth ? 'smooth' : 'auto' })
}

const isLatestAssistantMessage = (messageId: number) => {
  const latestAssistant = [...messages.value].reverse().find((item) => item.role === 'assistant')
  return latestAssistant?.id === messageId
}

const loadSessions = async () => {
  sessions.value = await listChatSessions({ mode: 'general' })
  if (!currentSessionId.value && sessions.value.length) {
    await selectSession(sessions.value[0].id)
  }
}

const createSession = async () => {
  const session = await createChatSession({ mode: 'general' })
  sessions.value.unshift(session)
  await selectSession(session.id)
}

const selectSession = async (sessionId: number) => {
  currentSessionId.value = sessionId
  messages.value = await listChatMessages(sessionId)
  assistantAnswer.value = [...messages.value].reverse().find((item) => item.role === 'assistant')?.content || ''
  await scrollToBottom()
}

const sendQuestion = async () => {
  if (!currentSessionId.value || !question.value.trim()) return
  streaming.value = true
  assistantAnswer.value = ''
  lastQuestion.value = question.value

  const trimmedQuestion = question.value.trim()
  const tempUserMessage: ChatMessageItem = {
    id: Date.now(),
    session_id: currentSessionId.value,
    role: 'user',
    content: trimmedQuestion,
    content_type: 'text',
    status: 'done',
    citations: [],
    meta: null,
    error_message: null,
    parent_message_id: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  }

  messages.value = [...messages.value, tempUserMessage]
  question.value = ''
  await scrollToBottom(true)

  abortController = new AbortController()
  try {
    const response = await createStreamRequest(currentSessionId.value, { message: trimmedQuestion }, abortController.signal)
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
          const assistantMessage: ChatMessageItem = {
            id: payload.message_id,
            session_id: currentSessionId.value,
            role: 'assistant',
            content: '',
            content_type: 'text',
            status: 'streaming',
            citations: [],
            meta: null,
            error_message: null,
            parent_message_id: null,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          }
          localMessages = [...localMessages, assistantMessage]
          messages.value = localMessages
          await scrollToBottom(true)
        } else if (payload.type === 'delta' && assistantMessageId) {
          assistantAnswer.value += payload.content || ''
          const target = localMessages.find((item) => item.id === assistantMessageId)
          if (target) {
            target.content = assistantAnswer.value
            messages.value = [...localMessages]
            await scrollToBottom()
          }
        } else if (payload.type === 'message_end') {
          assistantAnswer.value = payload.answer || assistantAnswer.value
          const target = localMessages.find((item) => item.id === assistantMessageId)
          if (target) {
            target.content = assistantAnswer.value
            target.status = 'done'
            target.citations = payload.citations || []
          }
          messages.value = [...localMessages]
          const currentSession = sessions.value.find((item) => item.id === currentSessionId.value)
          if (currentSession) {
            currentSession.last_message_at = new Date().toISOString()
            currentSession.message_count += 2
          }
          sessions.value = [...sessions.value]
          await scrollToBottom(true)
        } else if (payload.type === 'error') {
          throw new Error(payload.error || '生成失败')
        }
      }
    }
  } catch (error: any) {
    messages.value = messages.value.filter((item) => item.id !== tempUserMessage.id)
    if (error?.name !== 'AbortError') {
      ElMessage.error(error?.message || '生成失败')
      question.value = trimmedQuestion
    }
  } finally {
    streaming.value = false
  }
}

const stopStream = () => {
  abortController?.abort()
  streaming.value = false
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
  await loadSessions()
  if (!sessions.value.length) {
    await createSession()
  }
}

const handleInputKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    if (!streaming.value && currentSessionId.value && question.value.trim()) {
      void sendQuestion()
    }
  }
}

const formatTime = (value: string) => new Date(value).toLocaleString()

watch(
  () => messages.value.length,
  async () => {
    await scrollToBottom()
  },
)

onMounted(async () => {
  await loadSessions()
  if (!sessions.value.length) {
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
  grid-template-columns: 280px 1fr;
  gap: 20px;
  min-height: 760px;
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
  border-radius: 12px;
  padding: 12px;
  cursor: pointer;
  background: #fff;
  transition: all 0.2s ease;
}

.session-item:hover {
  border-color: #bfdcff;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.06);
}

.session-item.active {
  border-color: #409eff;
  background: linear-gradient(180deg, #f0f7ff 0%, #ecf5ff 100%);
}

.session-title {
  font-weight: 600;
}

.session-meta {
  margin-top: 6px;
  font-size: 12px;
  color: #6b7280;
}

.chat-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
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

.message-list {
  flex: 1;
  min-height: 0;
  max-height: 560px;
  overflow-y: auto;
  padding: 8px 6px 8px 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.empty-state {
  margin: auto;
  min-height: 220px;
  display: grid;
  place-items: center;
  text-align: center;
  color: #6b7280;
  border: 1px dashed #dbe4f0;
  border-radius: 18px;
  background: linear-gradient(180deg, #fbfdff 0%, #f7faff 100%);
}

.empty-state__title {
  font-size: 18px;
  font-weight: 700;
  color: #111827;
}

.empty-state__desc {
  margin-top: 8px;
  font-size: 13px;
}

.message-row {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.message-row--user {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-size: 13px;
  font-weight: 700;
  flex-shrink: 0;
  color: #fff;
  background: linear-gradient(135deg, #409eff 0%, #2563eb 100%);
  box-shadow: 0 8px 18px rgba(64, 158, 255, 0.28);
}

.message-row--assistant .message-avatar {
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  box-shadow: 0 8px 18px rgba(99, 102, 241, 0.25);
}

.message-bubble {
  max-width: min(82%, 880px);
  border-radius: 18px;
  padding: 14px 16px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
}

.message-bubble--user {
  background: linear-gradient(135deg, #409eff 0%, #5aa9ff 100%);
  color: #fff;
  border-top-right-radius: 8px;
}

.message-bubble--assistant {
  background: #f8fafc;
  border: 1px solid #e5edf7;
  color: #1f2937;
  border-top-left-radius: 8px;
}

.message-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  font-size: 13px;
}

.message-role-tip {
  font-size: 12px;
  opacity: 0.72;
}

.message-content {
  margin-top: 10px;
}

.message-text {
  white-space: pre-wrap;
  line-height: 1.8;
  word-break: break-word;
}

.composer-card {
  border: 1px solid #e5edf7;
  border-radius: 18px;
  padding: 16px;
  background: linear-gradient(180deg, #ffffff 0%, #fafcff 100%);
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05);
}

.composer-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.composer-title {
  font-size: 15px;
  font-weight: 700;
  color: #111827;
}

.composer-subtitle {
  margin-top: 4px;
  font-size: 12px;
  color: #6b7280;
}

.composer-input :deep(.el-textarea__inner) {
  border-radius: 14px;
  min-height: 110px;
  line-height: 1.75;
  padding: 14px 16px;
  box-shadow: none;
}

.composer-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 14px;
}

.composer-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.composer-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: #6b7280;
}

.stream-indicator {
  color: #409eff;
  font-weight: 600;
}

@media (max-width: 1024px) {
  .chat-shell {
    grid-template-columns: 1fr;
  }

  .session-panel {
    border-right: none;
    border-bottom: 1px solid #ebeef5;
    padding-right: 0;
    padding-bottom: 16px;
  }

  .message-bubble {
    max-width: 100%;
  }
}

@media (max-width: 768px) {
  .chat-page {
    margin: 16px;
  }

  .message-list {
    max-height: none;
  }

  .composer-head,
  .composer-footer {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
