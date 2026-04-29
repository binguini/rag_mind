<template>
  <div style="max-width: 960px; margin: 24px auto;">
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap;">
          <span>知识库管理</span>
          <div style="display: flex; gap: 8px; flex-wrap: wrap;">
            <el-button size="small" @click="$router.push('/chat')">知识库对话</el-button>
            <el-button size="small" @click="$router.push('/documents')">文档管理</el-button>
            <el-button size="small" @click="$router.push('/rag-debug')">RAG 调试</el-button>
            <el-button size="small" @click="$router.push('/settings/models')">模型设置</el-button>
          </div>
        </div>
      </template>
      <el-form :model="createForm" inline>
        <el-form-item label="名称">
          <el-input v-model="createForm.name" placeholder="输入知识库名称" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="createKb">创建</el-button>
          <el-button @click="loadData">刷新</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="rows" style="width: 100%; margin-top: 16px;">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="is_public" label="公开" width="100">
          <template #default="scope">{{ scope.row.is_public ? '是' : '否' }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="220" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { apiClient } from '../api/client'

const rows = ref<any[]>([])
const createForm = reactive({ name: '', description: '', is_public: false, system_prompt: '你是一个专业的知识库问答助手。' })

const loadData = async () => {
  try {
    const { data } = await apiClient.get('/knowledge-bases')
    rows.value = data
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '加载失败，请先登录')
  }
}

const createKb = async () => {
  if (!createForm.name.trim()) {
    ElMessage.warning('请输入知识库名称')
    return
  }
  try {
    await apiClient.post('/knowledge-bases', createForm)
    ElMessage.success('创建成功')
    createForm.name = ''
    await loadData()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '创建失败')
  }
}

onMounted(loadData)
</script>
