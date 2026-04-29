<template>
  <div class="user-settings-page">
    <el-card class="user-settings-card">
      <template #header>
        <div class="header-row">
          <div>
            <div class="title">用户信息设置</div>
            <div class="subtitle">设置头像、昵称和签名</div>
          </div>
          <el-button @click="router.push('/chat')">返回对话</el-button>
        </div>
      </template>

      <div v-loading="loading" class="settings-body">
        <div class="profile-preview">
          <el-avatar :size="72" :src="avatarPreviewUrl">
            {{ previewInitial }}
          </el-avatar>
          <div class="preview-text">
            <div class="preview-name">{{ previewName }}</div>
            <div class="preview-signature">{{ form.signature || '还没有签名' }}</div>
          </div>
        </div>

        <el-form label-width="90px" class="settings-form">
          <el-form-item label="头像">
            <div class="avatar-upload-row">
              <el-upload
                :auto-upload="false"
                :show-file-list="false"
                accept="image/*"
                :on-change="handleAvatarFileChange"
              >
                <el-button>选择本地头像</el-button>
              </el-upload>
              <el-button v-if="avatarFile" text @click="clearAvatarFile">取消本地头像</el-button>
              <el-input v-model="form.avatar_url" placeholder="输入头像图片 URL" clearable />
            </div>
          </el-form-item>
          <el-form-item label="昵称">
            <el-input v-model="form.nickname" placeholder="输入昵称" maxlength="80" show-word-limit />
          </el-form-item>
          <el-form-item label="签名">
            <el-input
              v-model="form.signature"
              type="textarea"
              :rows="4"
              placeholder="输入个性签名"
              maxlength="500"
              show-word-limit
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="saving" @click="handleSave">保存信息</el-button>
            <el-button @click="loadProfile">重置</el-button>
          </el-form-item>
        </el-form>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { getCurrentUser } from '../api/users'
import { useCurrentUserStore } from '../stores/currentUser'

const router = useRouter()
const userStore = useCurrentUserStore()
const loading = ref(false)
const saving = ref(false)
const avatarFile = ref<File | null>(null)
const initialForm = {
  avatar_url: '',
  nickname: '',
  signature: '',
}
const form = reactive({ ...initialForm })

const previewName = computed(() => form.nickname?.trim() || '未设置昵称')
const previewInitial = computed(() => previewName.value.slice(0, 1).toUpperCase() || 'U')
const avatarPreviewUrl = computed(() => form.avatar_url || undefined)

const clearAvatarFile = () => {
  avatarFile.value = null
}

const readFileAsDataUrl = (file: File) =>
  new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(new Error('读取头像文件失败'))
    reader.readAsDataURL(file)
  })

const handleAvatarFileChange = async (file: any) => {
  const raw = file.raw as File
  if (!raw) return
  avatarFile.value = raw
  try {
    form.avatar_url = await readFileAsDataUrl(raw)
    ElMessage.success('本地头像已加载，保存后生效')
  } catch (error: any) {
    ElMessage.error(error?.message || '读取头像文件失败')
  }
}

const applyProfile = (profile: Awaited<ReturnType<typeof getCurrentUser>>) => {
  form.avatar_url = profile.avatar_url || ''
  form.nickname = profile.nickname || ''
  form.signature = profile.signature || ''
}

const loadProfile = async () => {
  loading.value = true
  try {
    const profile = await getCurrentUser()
    applyProfile(profile)
    userStore.setProfile(profile)
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '加载用户信息失败')
  } finally {
    loading.value = false
  }
}

const handleSave = async () => {
  saving.value = true
  try {
    const profile = await userStore.updateProfile({
      avatar_url: form.avatar_url.trim() || null,
      nickname: form.nickname.trim() || null,
      signature: form.signature.trim() || null,
    })
    ElMessage.success('用户信息已保存')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(loadProfile)
onBeforeUnmount(() => {
  clearAvatarFile()
})
</script>

<style scoped>
.user-settings-page {
  max-width: 920px;
  margin: 24px auto;
  padding: 0 16px;
}

.user-settings-card {
  border-radius: 16px;
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.title {
  font-size: 20px;
  font-weight: 700;
}

.subtitle {
  margin-top: 4px;
  color: #6b7280;
  font-size: 13px;
}

.settings-body {
  display: grid;
  gap: 24px;
}

.profile-preview {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
  background: #fafafa;
}

.preview-text {
  display: grid;
  gap: 6px;
}

.preview-name {
  font-size: 18px;
  font-weight: 700;
}

.preview-signature {
  color: #6b7280;
}
</style>
