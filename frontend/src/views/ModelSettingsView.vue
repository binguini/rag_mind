<template>
  <div style="max-width: 900px; margin: 24px auto;">
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap;">
          <span>模型与检索配置</span>
          <div style="display: flex; gap: 8px; flex-wrap: wrap;">
            <el-button size="small" @click="$router.push('/chat')">聊天中心</el-button>
            <el-button size="small" @click="$router.push('/knowledge-bases')">知识库管理</el-button>
            <el-button size="small" @click="$router.push('/documents')">文档管理</el-button>
          </div>
        </div>
      </template>
      <el-form :model="form" label-width="180px">
        <el-form-item label="LLM Provider">
          <el-select v-model="form.llm_provider">
            <el-option label="openai_compatible" value="openai_compatible" />
            <el-option label="local" value="local" />
          </el-select>
        </el-form-item>
        <el-form-item label="LLM Model">
          <el-input v-model="form.llm_model" />
        </el-form-item>
        <el-form-item label="LLM Base URL">
          <el-input v-model="form.llm_base_url" />
        </el-form-item>
        <el-form-item label="LLM API Key">
          <el-input v-model="form.llm_api_key" show-password />
        </el-form-item>
        <el-form-item label="Embedding Provider">
          <el-select v-model="form.embedding_provider">
            <el-option label="local" value="local" />
            <el-option label="qwen" value="qwen" />
            <el-option label="ernie" value="ernie" />
          </el-select>
        </el-form-item>
        <el-form-item label="Embedding Model">
          <el-input v-model="form.embedding_model_name" />
        </el-form-item>
        <el-form-item label="TopK">
          <el-input-number v-model="form.retrieval_top_k" :min="1" :max="50" />
        </el-form-item>
        <el-form-item label="阈值">
          <el-input-number v-model="form.retrieval_threshold" :min="0" :max="1" :step="0.05" />
        </el-form-item>
        <el-form-item label="历史窗口">
          <el-input-number v-model="form.history_window" :min="0" :max="20" />
        </el-form-item>
        <el-form-item label="Qwen API Key">
          <el-input v-model="form.qwen_api_key" show-password />
        </el-form-item>
        <el-form-item label="Ernie API Key">
          <el-input v-model="form.ernie_api_key" show-password />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="save">保存</el-button>
          <el-button @click="load">刷新</el-button>
          <el-button @click="testLLM">测试 LLM</el-button>
          <el-button @click="testEmbedding">测试 Embedding</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { apiClient } from '../api/client'

const form = reactive({
  llm_provider: 'openai_compatible',
  llm_model: 'gpt-4o-mini',
  llm_base_url: 'https://xiaoai.plus/v1',
  llm_api_key: '',
  embedding_provider: 'local',
  embedding_model_name: 'bge-small-zh',
  retrieval_top_k: 8,
  retrieval_threshold: 0.65,
  history_window: 4,
  qwen_api_key: '',
  ernie_api_key: '',
})

const load = async () => {
  const { data } = await apiClient.get('/admin/model-config')
  Object.assign(form, data)
}

const save = async () => {
  await apiClient.put('/admin/model-config', form)
  ElMessage.success('保存成功')
}

const testLLM = async () => {
  await apiClient.post('/admin/test-llm', {
    provider: form.llm_provider,
    api_key: form.llm_api_key,
    base_url: form.llm_base_url,
    model: form.llm_model,
  })
  ElMessage.success('LLM 测试成功')
}

const testEmbedding = async () => {
  await apiClient.post('/admin/test-embedding', { provider: form.embedding_provider, api_key: form.qwen_api_key || form.ernie_api_key || '' })
  ElMessage.success('Embedding 测试成功')
}

onMounted(load)
</script>
