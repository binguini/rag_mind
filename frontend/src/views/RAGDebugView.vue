<template>
  <div class="rag-debug-page">
    <div class="page-head">
      <div>
        <div class="page-title">RAG 调试面板</div>
        <div class="page-subtitle">用于快速查看检索、重写、rerank、Prompt 与引用链路</div>
      </div>
      <div class="page-actions">
        <el-button size="small" @click="$router.push('/chat')">返回聊天</el-button>
        <el-button size="small" @click="$router.push('/knowledge-bases')">知识库管理</el-button>
      </div>
    </div>

    <el-alert
      v-if="!debugAccessEnabled"
      title="当前账号未开启调试模式访问权限"
      type="warning"
      :closable="false"
      description="调试面板需要后台开关开启，并将当前用户加入允许名单。"
    />

    <template v-else>
      <el-card class="toolbar-card">
        <template #header>
          <div class="toolbar-header">
            <span>筛选条件</span>
            <el-button text type="primary" @click="filtersCollapsed = !filtersCollapsed">
              {{ filtersCollapsed ? '展开' : '折叠' }}
            </el-button>
          </div>
        </template>
        <el-collapse-transition>
          <div v-show="!filtersCollapsed">
            <el-form :model="filters" :inline="true" class="filter-form">
              <el-form-item label="知识库">
                <el-select v-model="filters.knowledgeBaseId" placeholder="选择知识库" class="filter-field" @change="handleKnowledgeBaseChange">
                  <el-option v-for="kb in knowledgeBases" :key="kb.id" :label="kb.name" :value="kb.id" />
                </el-select>
              </el-form-item>
              <el-form-item label="会话 ID">
                <el-input-number v-model="filters.sessionId" :min="1" placeholder="可选" class="filter-field" />
              </el-form-item>
              <el-form-item label="问题关键词">
                <el-input v-model="filters.question" placeholder="搜索原始问题或改写问题" class="filter-field filter-field--wide" />
              </el-form-item>
              <el-form-item label="阶段">
                <el-select v-model="filters.stage" clearable placeholder="全部" class="filter-field">
                  <el-option label="completed" value="completed" />
                  <el-option label="failed" value="failed" />
                </el-select>
              </el-form-item>
              <el-form-item label="bad case">
                <el-select v-model="filters.badCaseFilter" clearable placeholder="全部" class="filter-field">
                  <el-option label="仅 bad case" value="true" />
                  <el-option label="仅非 bad case" value="false" />
                </el-select>
              </el-form-item>
              <el-form-item label="分类">
                <el-select v-model="filters.badCaseCategory" clearable placeholder="全部" class="filter-field">
                  <el-option label="召回不足" value="retrieval_miss" />
                  <el-option label="rerank 异常" value="rerank_issue" />
                  <el-option label="引用不准" value="citation_issue" />
                  <el-option label="回答幻觉" value="generation_hallucination" />
                  <el-option label="其他" value="other" />
                </el-select>
              </el-form-item>
              <el-form-item label="开始时间">
                <el-date-picker v-model="filters.startAt" type="datetime" placeholder="开始时间" value-format="YYYY-MM-DDTHH:mm:ss" class="filter-field" />
              </el-form-item>
              <el-form-item label="结束时间">
                <el-date-picker v-model="filters.endAt" type="datetime" placeholder="结束时间" value-format="YYYY-MM-DDTHH:mm:ss" class="filter-field" />
              </el-form-item>
              <el-form-item class="filter-actions">
                <el-button type="primary" @click="reloadLogsFromFirstPage">查询日志</el-button>
                <el-button @click="handleExportBadCases">导出 bad case</el-button>
              </el-form-item>
            </el-form>
          </div>
        </el-collapse-transition>
      </el-card>

      <div class="debug-layout">
        <div class="debug-left">
          <div class="tool-panel-group-shell">
            <div class="tool-panel-group-title">工具面板组</div>
            <div class="tool-panel-group">
              <el-card v-if="debugPolicy.can_manage" class="section-card section-card--group">
                <template #header>
                  <div class="toolbar-header">
                    <span>调试访问控制</span>
                    <el-button text type="primary" @click="accessCollapsed = !accessCollapsed">
                      {{ accessCollapsed ? '展开' : '折叠' }}
                    </el-button>
                  </div>
                </template>
                <el-collapse-transition>
                  <div v-show="!accessCollapsed" class="section-scroll">
                    <el-form label-width="160px" class="section-form section-form--spacious">
                      <el-form-item label="启用调试模式">
                        <el-switch v-model="debugPolicy.enabled" />
                      </el-form-item>
                      <el-form-item label="允许访问用户 ID 列表">
                        <el-input v-model="debugPolicy.allowed_user_ids_text" placeholder="例如：1,2,3" />
                      </el-form-item>
                      <el-form-item class="section-actions section-actions--sticky">
                        <el-button type="primary" @click="saveDebugPolicy">保存访问策略</el-button>
                      </el-form-item>
                    </el-form>
                  </div>
                </el-collapse-transition>
              </el-card>

              <el-card v-if="filters.knowledgeBaseId" class="section-card section-card--group section-card--config">
                <template #header>
                  <div class="toolbar-header">
                    <span>检索参数配置</span>
                    <el-button text type="primary" @click="configCollapsed = !configCollapsed">
                      {{ configCollapsed ? '展开' : '折叠' }}
                    </el-button>
                  </div>
                </template>
                <div class="config-shell">
                  <el-collapse-transition>
                    <div v-show="!configCollapsed" class="section-scroll">
                      <el-form :model="configForm" label-width="130px" class="section-form section-form--spacious">
                        <el-form-item label="保存范围">
                          <el-radio-group v-model="configForm.scope">
                            <el-radio label="knowledge_base">知识库级</el-radio>
                            <el-radio label="session">会话级</el-radio>
                          </el-radio-group>
                        </el-form-item>
                        <el-form-item label="top_k">
                          <el-input-number v-model="configForm.top_k" :min="1" :max="50" />
                        </el-form-item>
                        <el-form-item label="threshold">
                          <el-input-number v-model="configForm.threshold" :min="0" :max="1" :step="0.05" :precision="2" />
                        </el-form-item>
                        <el-form-item label="rerank 开关">
                          <el-switch v-model="configForm.rerank_enabled" />
                        </el-form-item>
                        <el-form-item label="chunk size">
                          <el-input-number v-model="configForm.chunk_size" :min="100" :max="4000" :step="50" />
                        </el-form-item>
                        <el-form-item label="chunk overlap">
                          <el-input-number v-model="configForm.chunk_overlap" :min="0" :max="2000" :step="20" />
                        </el-form-item>
                        <el-form-item class="section-actions section-actions--sticky">
                          <el-button type="primary" @click="saveConfig">保存配置</el-button>
                          <el-button @click="loadConfig">刷新</el-button>
                        </el-form-item>
                      </el-form>
                    </div>
                  </el-collapse-transition>
                </div>
              </el-card>

              <el-card class="section-card section-card--group">
                <template #header>问答调试日志</template>
                <el-table :data="logs" style="width: 100%" height="420" @row-click="selectLog">
                  <el-table-column prop="id" label="ID" width="80" />
                  <el-table-column label="bad case" width="110">
                    <template #default="scope">
                      <el-tag :type="scope.row.is_bad_case ? 'danger' : 'info'">{{ scope.row.is_bad_case ? '是' : '否' }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="分类" width="150">
                    <template #default="scope">{{ categoryLabel(scope.row.bad_case_category) }}</template>
                  </el-table-column>
                  <el-table-column prop="question" label="原始问题" min-width="220" show-overflow-tooltip />
                  <el-table-column prop="rewritten_question" label="改写后问题" min-width="220" show-overflow-tooltip />
                  <el-table-column label="阶段" width="110">
                    <template #default="scope">{{ scope.row.generation_stage || '-' }}</template>
                  </el-table-column>
                  <el-table-column label="总耗时(ms)" width="120">
                    <template #default="scope">{{ scope.row.total_duration_ms ?? '-' }}</template>
                  </el-table-column>
                  <el-table-column prop="created_at" label="创建时间" width="200" />
                  <el-table-column label="操作" width="140" fixed="right">
                    <template #default="scope">
                      <el-button size="small" :type="scope.row.is_bad_case ? 'warning' : 'danger'" @click.stop="openBadCaseDialog(scope.row)">
                        {{ scope.row.is_bad_case ? '编辑 bad case' : '标记 bad case' }}
                      </el-button>
                    </template>
                  </el-table-column>
                </el-table>

                <div style="display: flex; justify-content: flex-end; margin-top: 16px;">
                  <el-pagination
                    background
                    layout="total, prev, pager, next, sizes"
                    :total="total"
                    :page-size="pageSize"
                    :current-page="currentPage"
                    :page-sizes="[10, 20, 50, 100]"
                    @current-change="handleCurrentPageChange"
                    @size-change="handlePageSizeChange"
                  />
                </div>
              </el-card>
            </div>
          </div>
        </div>

        <div class="debug-right">
          <el-card v-if="selectedLog" class="detail-card">
            <template #header>
              <div class="detail-header">
                <div>
                  <div class="detail-title">RAG 调试视图</div>
                  <div class="detail-subtitle">点击左侧任意日志查看完整链路</div>
                </div>
                <div class="detail-tags">
                  <el-tag :type="selectedLog.is_bad_case ? 'danger' : 'info'">
                    {{ selectedLog.is_bad_case ? 'bad case' : 'normal' }}
                  </el-tag>
                  <el-tag v-if="selectedLog.bad_case_category" effect="plain">{{ categoryLabel(selectedLog.bad_case_category) }}</el-tag>
                </div>
              </div>
            </template>

            <el-descriptions :column="2" border class="detail-descriptions">
              <el-descriptions-item label="原始问题">{{ selectedLog.question }}</el-descriptions-item>
              <el-descriptions-item label="改写后问题">{{ selectedLog.rewritten_question || '-' }}</el-descriptions-item>
              <el-descriptions-item label="总耗时">{{ selectedLog.total_duration_ms ?? '-' }} ms</el-descriptions-item>
              <el-descriptions-item label="生成阶段">{{ selectedLog.generation_stage || '-' }}</el-descriptions-item>
              <el-descriptions-item label="重写耗时">{{ selectedLog.rewrite_duration_ms ?? '-' }} ms</el-descriptions-item>
              <el-descriptions-item label="检索耗时">{{ selectedLog.retrieval_duration_ms ?? '-' }} ms</el-descriptions-item>
              <el-descriptions-item label="rerank 耗时">{{ selectedLog.rerank_duration_ms ?? '-' }} ms</el-descriptions-item>
              <el-descriptions-item label="Prompt 构建耗时">{{ selectedLog.prompt_build_duration_ms ?? '-' }} ms</el-descriptions-item>
            </el-descriptions>

            <el-card v-if="selectedLog.is_bad_case" shadow="never" class="inner-card">
              <template #header>bad case 备注</template>
              <div><strong>分类：</strong>{{ categoryLabel(selectedLog.bad_case_category) }}</div>
              <div class="pre-wrap">{{ selectedLog.bad_case_note || '暂无备注' }}</div>
            </el-card>

            <el-tabs class="detail-tabs">
              <el-tab-pane label="检索参数">
                <pre class="debug-pre">{{ formatJson(selectedLog.retrieval_params) }}</pre>
              </el-tab-pane>
              <el-tab-pane label="检索命中文档列表">
                <pre class="debug-pre">{{ formatJson(selectedLog.retrieved_hits) }}</pre>
              </el-tab-pane>
              <el-tab-pane label="rerank 差异高亮">
                <div class="rerank-summary-grid">
                  <el-card shadow="never"><div class="summary-label">新进入结果集</div><div class="summary-value positive">{{ rerankSummary.enteredCount }}</div></el-card>
                  <el-card shadow="never"><div class="summary-label">移出结果集</div><div class="summary-value negative">{{ rerankSummary.exitedCount }}</div></el-card>
                  <el-card shadow="never"><div class="summary-label">排名上升</div><div class="summary-value positive">{{ rerankSummary.improvedCount }}</div></el-card>
                  <el-card shadow="never"><div class="summary-label">排名下降</div><div class="summary-value negative">{{ rerankSummary.droppedCount }}</div></el-card>
                </div>

                <div class="rerank-toolbar">
                  <el-switch v-model="rerankShowChangedOnly" active-text="仅看变化项" inactive-text="显示全部" />
                  <el-tag size="small" effect="plain">Prompt 注入高亮已开启</el-tag>
                </div>

                <div class="compare-grid" style="margin-top: 16px; align-items: start;">
                  <div>
                    <div class="compare-title">rerank 前</div>
                    <div v-for="item in visibleRerankBeforeDiffList" :key="`before-${item.chunk_id}`" class="rank-card" :class="[item.cardClass, { 'rank-card-injected': item.injectedIntoPrompt }]">
                      <div class="rank-card-header">
                        <div>
                          <span class="rank-badge">#{{ item.rank }}</span>
                          <strong>{{ item.document_name || `chunk ${item.chunk_id}` }}</strong>
                        </div>
                        <div class="rank-tags">
                          <el-tag v-if="item.statusLabel" size="small" :type="item.statusType">{{ item.statusLabel }}</el-tag>
                          <el-tag v-if="item.injectedIntoPrompt" size="small" type="primary" effect="dark">进入 Prompt</el-tag>
                          <el-tag v-if="item.deltaText" size="small" effect="plain">{{ item.deltaText }}</el-tag>
                        </div>
                      </div>
                      <div class="rank-meta">
                        chunk_id={{ item.chunk_id }} · fusion={{ formatScore(item.fusion_score) }} · vector={{ formatScore(item.vector_score) }} · bm25={{ formatScore(item.bm25_score) }}
                      </div>
                      <div class="rank-preview">{{ item.content || '-' }}</div>
                    </div>
                  </div>
                  <div>
                    <div class="compare-title">rerank 后</div>
                    <div v-for="item in visibleRerankAfterDiffList" :key="`after-${item.chunk_id}`" class="rank-card" :class="[item.cardClass, { 'rank-card-injected': item.injectedIntoPrompt }]">
                      <div class="rank-card-header">
                        <div>
                          <span class="rank-badge">#{{ item.rank }}</span>
                          <strong>{{ item.document_name || `chunk ${item.chunk_id}` }}</strong>
                        </div>
                        <div class="rank-tags">
                          <el-tag v-if="item.statusLabel" size="small" :type="item.statusType">{{ item.statusLabel }}</el-tag>
                          <el-tag v-if="item.injectedIntoPrompt" size="small" type="primary" effect="dark">进入 Prompt</el-tag>
                          <el-tag v-if="item.deltaText" size="small" effect="plain">{{ item.deltaText }}</el-tag>
                        </div>
                      </div>
                      <div class="rank-meta">
                        chunk_id={{ item.chunk_id }} · fusion={{ formatScore(item.fusion_score) }} · vector={{ formatScore(item.vector_score) }} · bm25={{ formatScore(item.bm25_score) }}
                      </div>
                      <div class="rank-preview">{{ item.content || '-' }}</div>
                    </div>
                  </div>
                </div>
              </el-tab-pane>
              <el-tab-pane label="最终 Prompt 上下文"><pre class="debug-pre">{{ formatJson(selectedLog.prompt_context) }}</pre></el-tab-pane>
              <el-tab-pane label="最终引用来源及命中依据">
                <div v-for="item in selectedLog.citations" :key="item.chunk_id" class="citation-card">
                  <div class="citation-title">{{ item.document_name }} / chunk {{ item.chunk_index }} / page {{ item.page ?? '-' }}</div>
                  <div class="citation-meta">
                    fusion={{ item.match_reason?.fusion_score ?? '-' }} |
                    vector={{ item.match_reason?.vector_score ?? '-' }} |
                    bm25={{ item.match_reason?.bm25_score ?? '-' }}
                  </div>
                  <div class="citation-content">{{ item.content }}</div>
                </div>
              </el-tab-pane>
              <el-tab-pane label="Prompt 文本"><pre class="debug-pre">{{ selectedLog.prompt_text || '-' }}</pre></el-tab-pane>
              <el-tab-pane label="错误信息"><pre class="debug-pre">{{ selectedLog.error_message || '-' }}</pre></el-tab-pane>
            </el-tabs>
          </el-card>
        </div>
      </div>
    </template>

    <el-dialog v-model="badCaseDialogVisible" title="bad case 标注" width="560px">
      <el-form :model="badCaseForm" label-width="100px">
        <el-form-item label="是否 bad case"><el-switch v-model="badCaseForm.is_bad_case" /></el-form-item>
        <el-form-item label="分类">
          <el-select v-model="badCaseForm.bad_case_category" clearable placeholder="请选择分类" style="width: 100%" :disabled="!badCaseForm.is_bad_case">
            <el-option label="召回不足" value="retrieval_miss" />
            <el-option label="rerank 异常" value="rerank_issue" />
            <el-option label="引用不准" value="citation_issue" />
            <el-option label="回答幻觉" value="generation_hallucination" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="badCaseForm.bad_case_note" type="textarea" :rows="5" maxlength="2000" show-word-limit :disabled="!badCaseForm.is_bad_case" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="badCaseDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitBadCaseDialog">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useCurrentUserStore } from '../stores/currentUser'
import { apiClient } from '../api/client'
import { getDebugAccessPolicy, updateDebugAccessPolicy } from '../api/debugAccess'
import {
  exportRagBadCases,
  getRetrievalConfig,
  listRagDebugLogs,
  markRagDebugBadCase,
  saveRetrievalConfig,
  type RAGDebugLogItem,
  type RetrievalConfigPayload,
} from '../api/ragDebug'

interface DiffRankItem {
  chunk_id: number
  rank: number
  document_name: string
  content: string
  fusion_score: number | null
  vector_score: number | null
  bm25_score: number | null
  statusLabel: string
  statusType: 'success' | 'danger' | 'warning' | 'info'
  deltaText: string
  cardClass: string
  changed: boolean
  injectedIntoPrompt: boolean
}

const { ensureLoaded, currentUser } = useCurrentUserStore()
const knowledgeBases = ref<any[]>([])
const logs = ref<RAGDebugLogItem[]>([])
const selectedLog = ref<RAGDebugLogItem | null>(null)
const debugAccessEnabled = ref(false)
const filtersCollapsed = ref(false)
const accessCollapsed = ref(false)
const configCollapsed = ref(false)
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const badCaseDialogVisible = ref(false)
const editingLogId = ref<number | null>(null)
const rerankShowChangedOnly = ref(false)
const filters = reactive({ knowledgeBaseId: undefined as number | undefined, sessionId: undefined as number | undefined, question: '', badCaseFilter: '' as '' | 'true' | 'false', badCaseCategory: '' as '' | 'retrieval_miss' | 'rerank_issue' | 'citation_issue' | 'generation_hallucination' | 'other', stage: '' as '' | 'completed' | 'failed', startAt: '', endAt: '' })
const debugPolicy = reactive({ enabled: false, can_manage: false, allowed_user_ids_text: '' })
const badCaseForm = reactive({ is_bad_case: true, bad_case_category: '' as '' | 'retrieval_miss' | 'rerank_issue' | 'citation_issue' | 'generation_hallucination' | 'other', bad_case_note: '' })
const parsedAllowedUserIds = computed(() => debugPolicy.allowed_user_ids_text.split(',').map((item) => Number(item.trim())).filter((item) => Number.isInteger(item) && item > 0))
const configForm = reactive<RetrievalConfigPayload>({ top_k: 8, threshold: 0.2, rerank_enabled: true, chunk_size: 800, chunk_overlap: 100, scope: 'knowledge_base' })
const formatJson = (value: unknown) => JSON.stringify(value ?? null, null, 2)
const formatScore = (value: unknown) => { if (value === null || value === undefined || value === '') return '-'; const num = Number(value); return Number.isFinite(num) ? num.toFixed(3) : String(value) }
const categoryLabel = (value: string | null | undefined) => ({ retrieval_miss: '召回不足', rerank_issue: 'rerank 异常', citation_issue: '引用不准', generation_hallucination: '回答幻觉', other: '其他' } as Record<string, string>)[value || ''] || '-'
const getChunkId = (item: Record<string, any>) => Number(item?.chunk_id)
const getDocumentName = (item: Record<string, any>) => item?.document_name || item?.filename || ''
const promptInjectedChunkIds = computed(() => { const ids = new Set<number>(); for (const item of selectedLog.value?.prompt_context || []) { const chunkId = Number(item?.chunk_id); if (Number.isFinite(chunkId) && chunkId > 0) ids.add(chunkId) } return ids })
const buildDiffList = (items: Array<Record<string, any>>, compareItems: Array<Record<string, any>>, side: 'before' | 'after'): DiffRankItem[] => { const currentRankMap = new Map<number, number>(); const compareRankMap = new Map<number, number>(); items.forEach((item, index) => currentRankMap.set(getChunkId(item), index + 1)); compareItems.forEach((item, index) => compareRankMap.set(getChunkId(item), index + 1)); return items.map((item, index) => { const chunkId = getChunkId(item); const currentRank = currentRankMap.get(chunkId) || index + 1; const compareRank = compareRankMap.get(chunkId); let statusLabel = '持平'; let statusType: DiffRankItem['statusType'] = 'info'; let deltaText = ''; let cardClass = 'rank-card-neutral'; if (!compareRank) { statusLabel = side === 'after' ? '新进入' : '被移出'; statusType = side === 'after' ? 'success' : 'danger'; deltaText = side === 'after' ? 'new' : 'out'; cardClass = side === 'after' ? 'rank-card-entered' : 'rank-card-exited' } else { const delta = compareRank - currentRank; if (delta > 0) { statusLabel = side === 'after' ? '排名上升' : '原排名较后'; statusType = 'success'; deltaText = `↑ ${Math.abs(delta)}`; cardClass = 'rank-card-improved' } else if (delta < 0) { statusLabel = side === 'after' ? '排名下降' : '原排名较前'; statusType = 'warning'; deltaText = `↓ ${Math.abs(delta)}`; cardClass = 'rank-card-dropped' } } return { chunk_id: chunkId, rank: currentRank, document_name: getDocumentName(item), content: item?.content || '', fusion_score: item?.fusion_score ?? item?.score ?? null, vector_score: item?.vector_score ?? null, bm25_score: item?.bm25_score ?? null, statusLabel, statusType, deltaText, cardClass, changed: statusLabel !== '持平', injectedIntoPrompt: promptInjectedChunkIds.value.has(chunkId) } }) }
const rerankBeforeDiffList = computed(() => buildDiffList(selectedLog.value?.rerank_before || [], selectedLog.value?.rerank_after || [], 'before'))
const rerankAfterDiffList = computed(() => buildDiffList(selectedLog.value?.rerank_after || [], selectedLog.value?.rerank_before || [], 'after'))
const visibleRerankBeforeDiffList = computed(() => rerankShowChangedOnly.value ? rerankBeforeDiffList.value.filter((item) => item.changed) : rerankBeforeDiffList.value)
const visibleRerankAfterDiffList = computed(() => rerankShowChangedOnly.value ? rerankAfterDiffList.value.filter((item) => item.changed) : rerankAfterDiffList.value)
const rerankSummary = computed(() => { const before = rerankBeforeDiffList.value; const after = rerankAfterDiffList.value; return { enteredCount: after.filter((item) => item.statusLabel === '新进入').length, exitedCount: before.filter((item) => item.statusLabel === '被移出').length, improvedCount: after.filter((item) => item.statusLabel === '排名上升').length, droppedCount: after.filter((item) => item.statusLabel === '排名下降').length } })
const loadKnowledgeBases = async () => { const { data } = await apiClient.get('/knowledge-bases'); knowledgeBases.value = data; if (!filters.knowledgeBaseId && data.length) filters.knowledgeBaseId = data[0].id }
const loadDebugPolicy = async () => { try { const data = await getDebugAccessPolicy(); debugPolicy.enabled = data.enabled; debugPolicy.can_manage = data.can_manage; debugPolicy.allowed_user_ids_text = data.allowed_user_ids.join(',') } catch { debugPolicy.can_manage = false } }
const saveDebugPolicy = async () => { try { const data = await updateDebugAccessPolicy({ enabled: debugPolicy.enabled, allowed_user_ids: parsedAllowedUserIds.value }); debugPolicy.enabled = data.enabled; debugPolicy.can_manage = data.can_manage; debugPolicy.allowed_user_ids_text = data.allowed_user_ids.join(','); ElMessage.success('调试访问策略已保存') } catch (error: any) { ElMessage.error(error?.response?.data?.detail || '保存访问策略失败') } }
const loadConfig = async () => { if (!filters.knowledgeBaseId) return; try { const data = await getRetrievalConfig(filters.knowledgeBaseId, filters.sessionId); configForm.top_k = data.top_k; configForm.threshold = data.threshold; configForm.rerank_enabled = data.rerank_enabled; configForm.chunk_size = data.chunk_size; configForm.chunk_overlap = data.chunk_overlap; configForm.scope = data.scope as 'knowledge_base' | 'session' } catch (error: any) { ElMessage.error(error?.response?.data?.detail || '加载配置失败') } }
const saveConfig = async () => { if (!filters.knowledgeBaseId) { ElMessage.warning('请先选择知识库'); return } if (configForm.scope === 'session' && !filters.sessionId) { ElMessage.warning('会话级配置需要填写会话 ID'); return } try { await saveRetrievalConfig(filters.knowledgeBaseId, configForm, filters.sessionId); ElMessage.success('保存成功'); await loadConfig() } catch (error: any) { ElMessage.error(error?.response?.data?.detail || '保存失败') } }
const loadLogs = async () => { try { const data = await listRagDebugLogs({ knowledge_base_id: filters.knowledgeBaseId, session_id: filters.sessionId, question: filters.question || undefined, is_bad_case: filters.badCaseFilter === '' ? undefined : filters.badCaseFilter === 'true', bad_case_category: filters.badCaseCategory || undefined, stage: filters.stage || undefined, start_at: filters.startAt || undefined, end_at: filters.endAt || undefined, limit: pageSize.value, offset: (currentPage.value - 1) * pageSize.value }); logs.value = data.items; total.value = data.total; selectedLog.value = data.items[0] || null } catch (error: any) { ElMessage.error(error?.response?.data?.detail || '加载日志失败') } }
const reloadLogsFromFirstPage = async () => { currentPage.value = 1; await loadLogs() }
const handleCurrentPageChange = async (page: number) => { currentPage.value = page; await loadLogs() }
const handlePageSizeChange = async (size: number) => { pageSize.value = size; currentPage.value = 1; await loadLogs() }
const handleKnowledgeBaseChange = async () => { selectedLog.value = null; currentPage.value = 1; await loadConfig(); await loadLogs() }
const selectLog = (row: RAGDebugLogItem) => { selectedLog.value = row }
const openBadCaseDialog = (row: RAGDebugLogItem) => { editingLogId.value = row.id; badCaseForm.is_bad_case = row.is_bad_case || false; badCaseForm.bad_case_category = (row.bad_case_category as any) || ''; badCaseForm.bad_case_note = row.bad_case_note || ''; badCaseDialogVisible.value = true }
const submitBadCaseDialog = async () => { if (!editingLogId.value) return; try { const updated = await markRagDebugBadCase(editingLogId.value, { is_bad_case: badCaseForm.is_bad_case, bad_case_category: badCaseForm.is_bad_case ? badCaseForm.bad_case_category : null, bad_case_note: badCaseForm.is_bad_case ? badCaseForm.bad_case_note : null }); ElMessage.success(updated.is_bad_case ? '已标记为 bad case' : '已取消 bad case 标记'); badCaseDialogVisible.value = false; await loadLogs() } catch (error: any) { ElMessage.error(error?.response?.data?.detail || '保存 bad case 失败') } }
const handleExportBadCases = async () => { try { const blob = await exportRagBadCases({ knowledge_base_id: filters.knowledgeBaseId }); const url = window.URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = 'rag_bad_cases.xlsx'; a.click(); window.URL.revokeObjectURL(url) } catch (error: any) { ElMessage.error(error?.response?.data?.detail || '导出失败') } }
onMounted(async () => { await ensureLoaded(); if (!currentUser.value) return; await loadKnowledgeBases(); await loadDebugPolicy(); if (filters.knowledgeBaseId) { await loadConfig(); await loadLogs() } debugAccessEnabled.value = true })
</script>

<style scoped>
.rag-debug-page { max-width: 1320px; margin: 24px auto; padding: 0 12px 24px; display: flex; flex-direction: column; gap: 16px; }
.page-head { display: flex; justify-content: space-between; gap: 12px; align-items: center; flex-wrap: wrap; }
.page-title { font-size: 22px; font-weight: 700; }
.page-subtitle { color: #6b7280; margin-top: 4px; }
.page-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.toolbar-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.toolbar-card, .section-card, .detail-card { border-radius: 12px; }
.debug-right .detail-card { height: 100%; overflow: auto; }
.section-card--group { overflow: hidden; }
.filter-form { display: flex; flex-wrap: wrap; gap: 0 12px; }
.filter-field { width: 220px; }
.filter-field--wide { width: 280px; }
.filter-actions { margin-left: auto; }
.debug-layout { display: grid; grid-template-columns: 420px minmax(0, 1fr); gap: 16px; align-items: start; }
.debug-left, .debug-right { display: flex; flex-direction: column; gap: 16px; min-width: 0; }
.debug-right { position: sticky; top: 24px; align-self: start; max-height: calc(100vh - 48px); }
.tool-panel-group-shell { border: 1px solid #e5e7eb; border-radius: 14px; background: linear-gradient(180deg, #fbfdff 0%, #ffffff 100%); padding: 12px; box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04); }
.tool-panel-group-title { font-size: 13px; font-weight: 700; color: #334155; letter-spacing: 0.04em; text-transform: uppercase; margin: 0 4px 12px; }
.tool-panel-group { display: flex; flex-direction: column; gap: 16px; }
.section-form { padding-right: 8px; }
.section-form--spacious { padding-right: 16px; padding-bottom: 8px; }
.section-scroll { overflow: visible; }
.section-card--group .el-card__body { padding-top: 0; }
.section-card--config .el-card__body { max-height: 380px; overflow: auto; }
.section-actions--sticky { position: sticky; bottom: 0; background: linear-gradient(to bottom, rgba(255,255,255,0.75), #fff 35%); padding-top: 8px; margin-bottom: 0; }
.detail-header { display: flex; justify-content: space-between; gap: 12px; align-items: center; flex-wrap: wrap; }
.detail-title { font-size: 18px; font-weight: 700; }
.detail-subtitle { color: #6b7280; font-size: 12px; margin-top: 4px; }
.detail-tags { display: flex; gap: 8px; flex-wrap: wrap; }
.detail-descriptions { margin-bottom: 16px; }
.inner-card { margin-top: 16px; }
.pre-wrap { margin-top: 8px; white-space: pre-wrap; color: #374151; }
.detail-tabs { margin-top: 16px; }
.detail-tabs :deep(.el-tabs__content) { overflow: auto; max-height: calc(100vh - 340px); }
.rerank-summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.summary-label { color: #6b7280; font-size: 12px; margin-bottom: 8px; }
.summary-value { font-size: 24px; font-weight: 700; }
.summary-value.positive { color: #16a34a; }
.summary-value.negative { color: #dc2626; }
.rerank-toolbar { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; margin-top: 12px; }
.compare-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.compare-title { font-weight: 700; margin-bottom: 10px; }
.rank-card { border: 1px solid #e5e7eb; border-radius: 10px; padding: 12px; margin-bottom: 12px; background: #fff; }
.rank-card-entered { border-color: #86efac; background: #f0fdf4; }
.rank-card-exited { border-color: #fca5a5; background: #fef2f2; }
.rank-card-improved { border-color: #93c5fd; background: #eff6ff; }
.rank-card-dropped { border-color: #fcd34d; background: #fffbeb; }
.rank-card-neutral { border-color: #e5e7eb; background: #ffffff; }
.rank-card-injected { box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.18); }
.rank-card-header { display: flex; justify-content: space-between; gap: 12px; align-items: center; flex-wrap: wrap; }
.rank-tags { display: flex; gap: 8px; flex-wrap: wrap; }
.rank-badge { display: inline-block; min-width: 38px; padding: 2px 8px; border-radius: 999px; background: #111827; color: #fff; font-size: 12px; margin-right: 8px; }
.rank-meta { color: #6b7280; font-size: 12px; margin-top: 8px; }
.rank-preview { margin-top: 10px; color: #374151; white-space: pre-wrap; }
.citation-card { border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; margin-bottom: 12px; }
.citation-title { font-weight: 600; margin-bottom: 6px; }
.citation-meta { color: #6b7280; font-size: 12px; margin-bottom: 8px; }
.citation-content { white-space: pre-wrap; color: #374151; }
.debug-pre { white-space: pre-wrap; background: #f8fafc; padding: 12px; border-radius: 8px; overflow: auto; max-height: 460px; }
@media (max-width: 1200px) { .debug-layout { grid-template-columns: 1fr; } .filter-field, .filter-field--wide { width: 100%; } .filter-actions { margin-left: 0; } .compare-grid, .rerank-summary-grid { grid-template-columns: 1fr; } }
</style>
