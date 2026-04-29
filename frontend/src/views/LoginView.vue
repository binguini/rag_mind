<template>
  <div class="login-page">
    <el-card class="login-card">
      <template #header>
        <div class="login-header">
          <div class="login-title">RAG Mind</div>
          <div class="login-subtitle">知识库问答与协作平台</div>
        </div>
      </template>

      <el-form :model="form" label-width="80px">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password placeholder="请输入密码" />
        </el-form-item>
        <div class="login-actions">
          <el-button type="primary" @click="handleLogin">登录</el-button>
          <el-button @click="handleRegister">注册</el-button>
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { apiClient } from '../api/client'
import { useCurrentUserStore } from '../stores/currentUser'

const router = useRouter()
const userStore = useCurrentUserStore()

const form = reactive({
  username: '',
  password: '',
})

const getErrorMessage = (error: any, fallback: string) => {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0]
    return first?.msg || fallback
  }
  return fallback
}

const validateBasic = () => {
  if (form.username.trim().length < 3) {
    ElMessage.warning('用户名至少 3 位')
    return false
  }
  if (form.password.length < 6) {
    ElMessage.warning('密码至少 6 位')
    return false
  }
  return true
}

const handleRegister = async () => {
  if (!validateBasic()) return
  try {
    await apiClient.post('/auth/register', form)
    ElMessage.success('注册成功，请登录')
  } catch (error: any) {
    ElMessage.error(getErrorMessage(error, '注册失败'))
  }
}

const handleLogin = async () => {
  if (!validateBasic()) return
  try {
    const { data } = await apiClient.post('/auth/login', form)
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    await userStore.ensureLoaded()
    ElMessage.success('登录成功')
    router.push('/chat')
  } catch (error: any) {
    ElMessage.error(getErrorMessage(error, '登录失败'))
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(circle at top, #eef2ff 0%, #f8fafc 48%, #e2e8f0 100%);
  padding: 24px;
}

.login-card {
  width: 100%;
  max-width: 440px;
  box-shadow: 0 20px 60px rgba(15, 23, 42, 0.12);
  border-radius: 16px;
}

.login-header {
  text-align: center;
}

.login-title {
  font-size: 28px;
  font-weight: 800;
  color: #111827;
}

.login-subtitle {
  margin-top: 8px;
  color: #6b7280;
  font-size: 14px;
}

.login-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}
</style>
