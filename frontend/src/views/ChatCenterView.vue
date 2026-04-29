<template>
  <div class="chat-center" :class="{ mobile: isMobile }">
    <el-card v-if="!isMobile || mobileSessionsOpen" class="session-panel" shadow="never">
      <template #header>
        <div class="panel-header">
          <span>会话</span>
          <div style="display: flex; gap: 8px; align-items: center;">
            <el-button size="small" text v-if="isMobile" @click="mobileSessionsOpen = false">收起</el-button>
            <el-button size="small" type="primary" plain @click="createSession">新建</el-button>
          </div>
        </div>
      </template>

      <div class="session-toolbar">
        <el-radio-group v-model="activeMode" size="small" @change="handleModeChange">
          <el-radio-button label="general">通用</el-radio-button>
          <el-radio-button label="rag">知识库</el-radio-button>
        </el-radio-group>

        <el-select
          v-if="activeMode === 'rag'"
          v-model="kbId"
          placeholder="选择知识库"
          size="small"
          style="width: 100%; margin-top: 10px;"
          @change="handleKnowledgeBaseChange"
        >
          <el-option v-for="kb in knowledgeBases" :key="kb.id" :label="kb.name" :value="kb.id" />
        </el-select>
      </div>

      <div class="session-list">
        <div
          v-for="session in sessions"
          :key="session.id"
          class="session-item"
          :class="{ active: session.id === activeSessionId }"
          @click="activateSession(session.id)"
        >
          <div class="session-avatar">{{ session.title.slice(0, 1) }}</div>
          <div class="session-item-main">
            <div class="session-title">{{ session.title }}</div>
            <div class="session-meta">
              <el-tag size="small" effect="plain">{{ session.mode === 'general' ? '通用对话' : '知识库对话' }}</el-tag>
            </div>
          </div>
          <el-dropdown trigger="click" @command="(cmd) => handleSessionCommand(cmd, session.id)">
            <el-button size="small" text class="session-more">···</el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="rename">重命名</el-dropdown-item>
                <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
    </el-card>

    <el-card class="chat-panel">
      <template #header>
        <div class="chat-header">
          <div>
            <div class="title-line">{{ activeSession?.title || '聊天中心' }}</div>
            <div class="subtitle-line">{{ activeModeLabel }}</div>
          </div>
          <div class="chat-actions">
            <el-button v-if="isMobile" size="small" @click="mobileSessionsOpen = !mobileSessionsOpen">
              {{ mobileSessionsOpen ? '隐藏会话' : '显示会话' }}
            </el-button>
            <el-tag effect="plain">{{ currentUserLabel }}</el-tag>
          </div>
        </div>
      </template>

      <div class="chat-quick-actions">
        <el-button size="small" @click="$router.push('/knowledge-bases')">知识库管理</el-button>
        <el-button size="small" @click="$router.push('/documents')">文档管理</el-button>
        <el-button v-if="activeMode === 'rag' && kbId && debugAccessEnabled" size="small" @click="showRetrievalConfigPanel = !showRetrievalConfigPanel">
          {{ showRetrievalConfigPanel ? '收起检索参数' : '检索参数' }}
        </el-button>
        <el-button v-if="debugAccessEnabled" size="small" @click="$router.push('/rag-debug')">RAG 调试</el-button>
        <el-button size="small" @click="$router.push('/settings/models')">模型设置</el-button>
      </div>

      <el-card v-if="activeMode === 'rag' && kbId && debugAccessEnabled" style="margin: 12px 0;" shadow="never">
        <template #header>
          <div class="rag-config-header">
            <span>当前检索参数</span>
            <el-tag size="small" effect="plain">来源：{{ retrievalConfig.sourceLabel }}</el-tag>
          </div>
        </template>
        <div class="rag-config-summary">
          <el-tag size="small">top_k={{ retrievalConfig.top_k }}</el-tag>
          <el-tag size="small">threshold={{ retrievalConfig.threshold }}</el-tag>
          <el-tag size="small">rerank={{ retrievalConfig.rerank_enabled ? 'on' : 'off' }}</el-tag>
          <el-tag size="small">chunk={{ retrievalConfig.chunk_size }}</el-tag>
          <el-tag size="small">overlap={{ retrievalConfig.chunk_overlap }}</el-tag>
        </div>
      </el-card>

      <el-card v-if="activeMode === 'rag' && kbId && debugAccessEnabled && showRetrievalConfigPanel" style="margin: 12px 0;" shadow="never">
        <template #header>会话内检索参数配置</template>
        <el-form :model="retrievalConfigForm" label-width="120px" class="rag-config-form">
          <el-form-item label="保存范围">
            <el-radio-group v-model="retrievalConfigForm.scope">
              <el-radio label="knowledge_base">知识库级</el-radio>
              <el-radio :disabled="!activeSessionId" label="session">会话级</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="top_k">
            <el-input-number v-model="retrievalConfigForm.top_k" :min="1" :max="50" />
          </el-form-item>
          <el-form-item label="threshold">
            <el-input-number v-model="retrievalConfigForm.threshold" :min="0" :max="1" :step="0.05" :precision="2" />
          </el-form-item>
          <el-form-item label="rerank">
            <el-switch v-model="retrievalConfigForm.rerank_enabled" />
          </el-form-item>
          <el-form-item label="chunk size">
            <el-input-number v-model="retrievalConfigForm.chunk_size" :min="100" :max="4000" :step="50" />
          </el-form-item>
          <el-form-item label="chunk overlap">
            <el-input-number v-model="retrievalConfigForm.chunk_overlap" :min="0" :max="2000" :step="20" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="retrievalConfigLoading" @click="saveInlineRetrievalConfig">保存</el-button>
            <el-button :loading="retrievalConfigLoading" @click="loadRetrievalConfig">刷新</el-button>
          </el-form-item>
        </el-form>
      </el-card>

      <el-card v-if="streaming" style="margin: 12px 0;" shadow="never">
        <template #header>生成中</template>
        <el-progress :percentage="streamProgress" :status="streamStatus" />
      </el-card>

      <div class="conversation-area" :class="{ 'with-citation-sidebar': citations.length && activeMode === 'rag' && showCitations && citationPlacement === 'side' && !isMobile }">
        <div ref="messageViewport" class="message-list">
          <div
            v-for="msg in activeSessionMessages.filter((item) => item.role !== 'assistant' || item.content?.trim() || item.status === 'streaming')"
            :key="msg.id"
            class="message-item"
            :class="msg.role"
          >
            <strong>{{ msg.role === 'user' ? '用户' : '助手' }}</strong>
            <div class="message-content" style="margin-top: 8px;">
              <div v-if="msg.role === 'user'" style="white-space: pre-wrap;">{{ msg.content }}</div>
              <MarkdownMessage v-else :content="msg.content" />
            </div>
          </div>
        </div>

        <div v-if="citations.length && activeMode === 'rag'" class="citation-toolbar">
          <el-button size="small" @click="handleToggleCitations">
            {{ showCitations ? '收起引用来源' : '显示引用来源' }}
          </el-button>
          <el-radio-group v-if="showCitations && !isMobile" v-model="citationPlacement" size="small">
            <el-radio-button label="bottom">下方</el-radio-button>
            <el-radio-button label="side">右侧</el-radio-button>
          </el-radio-group>
          <el-button v-if="showCitations && isMobile" size="small" @click="citationDrawerVisible = true">打开引用抽屉</el-button>
        </div>

        <el-card v-if="citations.length && activeMode === 'rag' && showCitations && (citationPlacement === 'bottom' || isMobile)" class="citation-panel-bottom" shadow="never">
          <template #header>引用来源</template>
          <el-timeline>
            <el-timeline-item v-for="item in citations" :key="item.chunk_id" :timestamp="`score: ${Number(item.score || 0).toFixed(3)}`">
              <div><strong>{{ item.document_name }}</strong> / chunk {{ item.chunk_index }} / page {{ item.page ?? '-' }}</div>
              <div class="citation-content">{{ item.content }}</div>
            </el-timeline-item>
          </el-timeline>
        </el-card>

        <el-card v-if="citations.length && activeMode === 'rag' && showCitations && citationPlacement === 'side' && !isMobile" class="citation-panel-side" shadow="never">
          <template #header>引用来源</template>
          <el-timeline>
            <el-timeline-item v-for="item in citations" :key="item.chunk_id" :timestamp="`score: ${Number(item.score || 0).toFixed(3)}`">
              <div><strong>{{ item.document_name }}</strong> / chunk {{ item.chunk_index }} / page {{ item.page ?? '-' }}</div>
              <div class="citation-content">{{ item.content }}</div>
            </el-timeline-item>
          </el-timeline>
        </el-card>
      </div>

      <el-drawer v-model="citationDrawerVisible" title="引用来源" size="85%" :with-header="true">
        <el-timeline v-if="citations.length">
          <el-timeline-item v-for="item in citations" :key="`drawer-${item.chunk_id}`" :timestamp="`score: ${Number(item.score || 0).toFixed(3)}`">
            <div><strong>{{ item.document_name }}</strong> / chunk {{ item.chunk_index }} / page {{ item.page ?? '-' }}</div>
            <div class="citation-content">{{ item.content }}</div>
          </el-timeline-item>
        </el-timeline>
      </el-drawer>

      <div class="composer-area">
        <el-divider />
        <el-input
          v-model="question"
          type="textarea"
          :rows="4"
          placeholder="请输入问题，例如：请总结今天会议的重点。"
          @keydown.enter.exact.prevent="sendQuestion"
          @keydown.enter.shift.exact.stop
        />

        <div class="toolbar">
          <el-button type="primary" :disabled="!question.trim() || streaming || (activeMode === 'rag' && !kbId) || !activeSessionId" @click="sendQuestion">
            {{ streaming ? '生成中...' : '发送' }}
          </el-button>
          <el-button :disabled="!streaming" @click="stopStream">停止生成</el-button>
          <el-button :disabled="!lastQuestion || streaming" @click="retryLast">重新生成</el-button>
          <el-button :disabled="!assistantAnswer" @click="copyAnswer">复制答案</el-button>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import MarkdownMessage from '../components/MarkdownMessage.vue'
import { useCurrentUserStore } from '../stores/currentUser'
import { apiClient } from '../api/client'
import { getRetrievalConfig, saveRetrievalConfig, type RetrievalConfigPayload } from '../api/ragDebug'
import {
  createChatSession,
  createStreamRequest,
  deleteChatSession,
  listChatMessages,
  listChatSessions,
  updateChatSession,
  type ChatMessageItem,
  type ChatSessionItem,
  type ChatMode,
} from '../api/chat'
import { getCurrentUserLabel } from '../utils/auth'

interface CitationItem {
  document_id: number
  document_name: string
  chunk_id: number
  chunk_index: number
  page: number | null
  score: number
  content: string
}

const { ensureLoaded, currentUser } = useCurrentUserStore()
const knowledgeBases = ref<any[]>([])
const kbId = ref<number | null>(null)
const activeMode = ref<ChatMode>('general')
const question = ref('')
const assistantAnswer = ref('')
const lastQuestion = ref('')
const streaming = ref(false)
const streamProgress = ref(0)
const streamStatus = ref<'success' | 'exception' | undefined>(undefined)
const citations = ref<CitationItem[]>([])
const sessions = ref<ChatSessionItem[]>([])
const activeSessionId = ref<number | null>(null)
const messages = ref<ChatMessageItem[]>([])
const mobileSessionsOpen = ref(false)
const isMobile = ref(false)
const messageViewport = ref<HTMLElement | null>(null)
const showCitations = ref(false)
const citationPlacement = ref<'bottom' | 'side'>('side')
const citationDrawerVisible = ref(false)
let abortController: AbortController | null = null

const currentUserLabel = computed(() => getCurrentUserLabel())
const currentKnowledgeBaseName = computed(() => knowledgeBases.value.find((item) => item.id === kbId.value)?.name || '未选择')
const activeSession = computed(() => sessions.value.find((item) => item.id === activeSessionId.value) || null)
const activeSessionMessages = computed(() => messages.value)
const debugAccessEnabled = computed(() => Boolean(currentUser.value?.debug_access_enabled))
const retrievalConfigLoading = ref(false)
const retrievalConfig = ref<RetrievalConfigPayload & { sourceLabel?: string }>({
  top_k: 8,
  threshold: 0.2,
  rerank_enabled: true,
  chunk_size: 800,
  chunk_overlap: 100,
  scope: 'knowledge_base',
  sourceLabel: '知识库级',
})
const retrievalConfigForm = ref<RetrievalConfigPayload>({
  top_k: 8,
  threshold: 0.2,
  rerank_enabled: true,
  chunk_size: 800,
  chunk_overlap: 100,
  scope: 'knowledge_base',
})
const showRetrievalConfigPanel = ref(false)
const activeModeLabel = computed(() => (activeMode.value === 'general' ? '通用对话' : `知识库对话 · ${currentKnowledgeBaseName.value}`))

const updateMobileState = () => {
  isMobile.value = window.innerWidth < 1100
  if (!isMobile.value) {
    mobileSessionsOpen.value = true
    citationDrawerVisible.value = false
  }
}

const scrollToBottom = async () => {
  await nextTick()
  const el = messageViewport.value
  if (el) el.scrollTop = el.scrollHeight
}

const handleToggleCitations = () => {
  showCitations.value = !showCitations.value
  if (!showCitations.value) {
    citationDrawerVisible.value = false
  } else if (isMobile.value) {
    citationDrawerVisible.value = true
  }
}

const loadKnowledgeBases = async () => {
  const { data } = await apiClient.get('/knowledge-bases')
  knowledgeBases.value = data
  if (!kbId.value && data.length > 0) kbId.value = data[0].id
}

const applyRetrievalConfig = (data: RetrievalConfigPayload & { scope: 'knowledge_base' | 'session' }) => {
  retrievalConfig.value = {
    ...data,
    sourceLabel: data.scope === 'session' ? '会话级' : '知识库级',
  }
  retrievalConfigForm.value = {
    top_k: data.top_k,
    threshold: data.threshold,
    rerank_enabled: data.rerank_enabled,
    chunk_size: data.chunk_size,
    chunk_overlap: data.chunk_overlap,
    scope: data.scope,
  }
}

const loadRetrievalConfig = async () => {
  if (!debugAccessEnabled.value || activeMode.value !== 'rag' || !kbId.value) return
  retrievalConfigLoading.value = true
  try {
    const data = await getRetrievalConfig(kbId.value, activeSessionId.value)
    applyRetrievalConfig(data)
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '加载检索参数失败')
  } finally {
    retrievalConfigLoading.value = false
  }
}

const saveInlineRetrievalConfig = async () => {
  if (!kbId.value) return
  if (retrievalConfigForm.value.scope === 'session' && !activeSessionId.value) {
    ElMessage.warning('当前没有可绑定的会话，无法保存会话级参数')
    return
  }
  retrievalConfigLoading.value = true
  try {
    const data = await saveRetrievalConfig(kbId.value, retrievalConfigForm.value, activeSessionId.value)
    applyRetrievalConfig(data)
    ElMessage.success('检索参数已保存')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '保存检索参数失败')
  } finally {
    retrievalConfigLoading.value = false
  }
}

const loadSessions = async () => {
  const params = activeMode.value === 'rag'
    ? { mode: 'rag' as ChatMode, knowledge_base_id: kbId.value || undefined }
    : { mode: 'general' as ChatMode }
  sessions.value = await listChatSessions(params)
  if (sessions.value.length > 0) {
    if (!activeSessionId.value || !sessions.value.some((item) => item.id === activeSessionId.value)) {
      await activateSession(sessions.value[0].id)
    }
  } else {
    activeSessionId.value = null
    messages.value = []
  }
}

const createSession = async () => {
  const payload = activeMode.value === 'rag'
    ? { mode: 'rag' as ChatMode, knowledge_base_id: kbId.value || undefined }
    : { mode: 'general' as ChatMode }
  const session = await createChatSession(payload)
  await loadSessions()
  await activateSession(session.id)
  if (activeMode.value === 'rag' && debugAccessEnabled.value) {
    await loadRetrievalConfig()
  }
  mobileSessionsOpen.value = false
}

const activateSession = async (sessionId: number) => {
  activeSessionId.value = sessionId
  const session = sessions.value.find((item) => item.id === sessionId)
  if (session) {
    activeMode.value = session.mode
    if (session.mode === 'rag' && session.knowledge_base_id) kbId.value = session.knowledge_base_id
  }
  messages.value = await listChatMessages(sessionId)
  const lastAssistant = [...messages.value].reverse().find((item) => item.role === 'assistant')
  assistantAnswer.value = lastAssistant?.content || ''
  citations.value = (lastAssistant?.citations || []) as CitationItem[]
  if (activeMode.value === 'rag' && debugAccessEnabled.value) {
    await loadRetrievalConfig()
  }
  if (isMobile.value) mobileSessionsOpen.value = false
}

const handleSessionCommand = async (command: string, sessionId: number) => {
  const session = sessions.value.find((item) => item.id === sessionId)
  if (!session) return

  if (command === 'rename') {
    const { value } = await ElMessageBox.prompt('请输入新的会话名称', '重命名会话', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputValue: session.title,
      inputPlaceholder: '会话名称',
      inputValidator: (v) => !!v.trim(),
      inputErrorMessage: '名称不能为空',
    })
    await updateChatSession(sessionId, { title: value.trim() })
    await loadSessions()
    ElMessage.success('已重命名')
  }

  if (command === 'delete') {
    await ElMessageBox.confirm(`确定删除会话「${session.title}」吗？`, '删除会话', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await deleteChatSession(sessionId)
    await loadSessions()
    if (!sessions.value.length) {
      await createSession()
    }
    ElMessage.success('已删除')
  }
}

const sendQuestion = async () => {
  if (!question.value.trim() || !activeSessionId.value) return
  if (activeMode.value === 'rag' && !kbId.value) return

  streaming.value = true
  streamProgress.value = 0
  streamStatus.value = undefined
  assistantAnswer.value = ''
  citations.value = []
  lastQuestion.value = question.value

  abortController = new AbortController()
  try {
    const response = await createStreamRequest(activeSessionId.value, { message: question.value }, abortController.signal)
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
          const existingAssistant = messages.value.find((item) => item.id === assistantMessageId)
          if (existingAssistant) {
            localMessages = [...messages.value]
          } else {
            const optimisticAssistant: ChatMessageItem = {
              id: assistantMessageId,
              session_id: activeSessionId.value,
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
            localMessages = [...messages.value, optimisticAssistant]
            messages.value = localMessages
          }
        } else if (payload.type === 'delta' && assistantMessageId) {
          assistantAnswer.value += payload.content || ''
          const target = localMessages.find((item) => item.id === assistantMessageId)
          if (target) {
            target.content = assistantAnswer.value
            messages.value = [...localMessages]
          }
          streamProgress.value = Math.min(95, streamProgress.value + 1)
          await scrollToBottom()
        } else if (payload.type === 'message_end') {
          assistantAnswer.value = payload.answer || assistantAnswer.value
          citations.value = (payload.citations || []) as CitationItem[]
          if (citations.value.length) {
            showCitations.value = true
            if (isMobile.value) {
              citationDrawerVisible.value = true
            }
          }

          if (assistantMessageId) {
            const target = localMessages.find((item) => item.id === assistantMessageId)
            if (target) {
              target.content = assistantAnswer.value
              target.citations = citations.value as Array<Record<string, any>>
              target.status = 'done'
            }
            messages.value = [...localMessages]
          }

          try {
            const latestMessages = await listChatMessages(activeSessionId.value)
            const latestAssistant = [...latestMessages].reverse().find((item) => item.id === assistantMessageId)
            if (latestAssistant) {
              assistantAnswer.value = latestAssistant.content || assistantAnswer.value
              citations.value = (latestAssistant.citations || citations.value) as CitationItem[]
              messages.value = latestMessages
            }
          } catch {
            // keep optimistic local state
          }

          await loadSessions()
          streamProgress.value = 100
          streamStatus.value = 'success'
          await scrollToBottom()
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

const handleModeChange = async () => {
  activeSessionId.value = null
  messages.value = []
  citations.value = []
  assistantAnswer.value = ''
  showRetrievalConfigPanel.value = false
  await loadSessions()
  if (!sessions.value.length) {
    await createSession()
  }
  if (activeMode.value === 'rag' && debugAccessEnabled.value) {
    await loadRetrievalConfig()
  }
}

const handleKnowledgeBaseChange = async () => {
  if (activeMode.value !== 'rag') return
  showRetrievalConfigPanel.value = false
  await loadSessions()
  if (!sessions.value.length) {
    await createSession()
  }
  if (debugAccessEnabled.value) {
    await loadRetrievalConfig()
  }
}

onMounted(async () => {
  updateMobileState()
  window.addEventListener('resize', updateMobileState)
  await ensureLoaded()
  await loadKnowledgeBases()
  if (!isMobile.value) mobileSessionsOpen.value = true
  await loadSessions()
  if (!sessions.value.length) {
    await createSession()
  }
  if (activeMode.value === 'rag' && debugAccessEnabled.value && kbId.value) {
    await loadRetrievalConfig()
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', updateMobileState)
})
</script>

<style scoped>
.chat-center {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 16px;
  max-width: 1400px;
  margin: 24px auto;
  align-items: stretch;
  height: calc(100vh - 130px);
  min-height: 0;
}
.session-panel,
.chat-panel {
  min-height: 0;
  height: 100%;
}
:deep(.session-panel > .el-card__body),
:deep(.chat-panel > .el-card__body) {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
}
.session-panel {
  background: #ffffff;
  border: 1px solid #e5e7eb;
  color: #111827;
}
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.session-toolbar {
  margin-bottom: 12px;
}
.session-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
  min-height: 0;
  overflow: auto;
}
.session-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.session-item:hover,
.session-item.active {
  background: #f3f7ff;
}
.session-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, #409eff, #67c23a);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
}
.session-item-main {
  flex: 1;
  min-width: 0;
}
.session-title {
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.session-meta {
  margin-top: 6px;
}
.chat-panel {
  display: flex;
  flex-direction: column;
}
.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.title-line {
  font-size: 18px;
  font-weight: 700;
}
.subtitle-line {
  font-size: 12px;
  color: #6b7280;
  margin-top: 4px;
}
.chat-actions,
.chat-quick-actions,
.toolbar,
.rag-config-summary,
.rag-config-header {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.rag-config-header {
  justify-content: space-between;
}

.rag-config-form {
  max-width: 720px;
}
.conversation-area {
  display: flex;
  flex-direction: column;
  min-height: 0;
  flex: 1;
  overflow: hidden;
}

.conversation-area.with-citation-sidebar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  grid-template-areas:
    'messages toolbar'
    'messages sidebar';
  gap: 12px;
  align-items: start;
}

.message-list {
  flex: 1;
  min-height: 0;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-right: 6px;
}

.conversation-area.with-citation-sidebar .message-list {
  grid-area: messages;
}
.message-item {
  padding: 14px 16px;
  border-radius: 14px;
  max-width: 86%;
}
.message-item.user {
  align-self: flex-end;
  background: #ecf5ff;
}
.message-item.assistant {
  align-self: flex-start;
  background: #f5f7fa;
}
.message-content,
.citation-content {
  white-space: pre-wrap;
  margin-top: 8px;
  color: #374151;
}

.citation-toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  margin-top: 12px;
}

.conversation-area.with-citation-sidebar .citation-toolbar {
  grid-area: toolbar;
  margin-top: 0;
}

.citation-panel-bottom {
  margin-top: 12px;
}

.citation-panel-side {
  grid-area: sidebar;
  min-height: 0;
  max-height: 100%;
  overflow: hidden;
}

.citation-panel-side :deep(.el-card__body) {
  max-height: calc(100vh - 380px);
  overflow: auto;
}

.composer-area {
  margin-top: 16px;
  flex-shrink: 0;
}
.mobile {
  grid-template-columns: 1fr;
  height: auto;
}
.mobile .session-panel,
.mobile .chat-panel {
  height: auto;
}
.mobile :deep(.session-panel > .el-card__body),
.mobile :deep(.chat-panel > .el-card__body) {
  height: auto;
}
.mobile .session-panel {
  order: 2;
}
.mobile .chat-panel {
  order: 1;
}
.mobile .conversation-area,
.mobile .message-list,
.mobile .session-list {
  overflow: visible;
}

.mobile .conversation-area.with-citation-sidebar {
  display: flex;
  grid-template-columns: none;
  grid-template-areas: none;
}
</style>
