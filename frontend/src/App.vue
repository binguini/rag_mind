<template>
  <el-container v-if="showShell" style="height: 100vh;">
    <el-header class="app-header">
      <div class="brand">RAG Mind</div>
      <div class="header-actions">
        <el-tag type="success" effect="light">{{ currentUserLabel }}</el-tag>
        <el-button size="small" @click="logout">退出登录</el-button>
      </div>
    </el-header>

    <el-container>
      <el-aside :width="collapsed ? '72px' : '240px'" class="app-aside">
        <div class="aside-toolbar">
          <el-button size="small" text @click="collapsed = !collapsed">
            {{ collapsed ? '展开' : '收起' }}
          </el-button>
        </div>
        <el-menu :default-active="activeMenu" router :collapse="collapsed" class="sidebar-menu">
          <el-sub-menu index="core">
            <template #title>核心功能</template>
            <el-menu-item index="/chat">聊天中心</el-menu-item>
            <el-menu-item index="/documents">文档管理</el-menu-item>
            <el-menu-item index="/knowledge-bases">知识库管理</el-menu-item>
          </el-sub-menu>
          <el-sub-menu index="config">
            <template #title>配置中心</template>
            <el-menu-item index="/settings/models">模型设置</el-menu-item>
          </el-sub-menu>
        </el-menu>
      </el-aside>

      <el-main class="app-main">
        <div class="breadcrumb-bar">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item>主页</el-breadcrumb-item>
            <el-breadcrumb-item>{{ routeTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <router-view v-slot="{ Component }">
          <component :is="Component" :key="route.fullPath" />
        </router-view>
      </el-main>
    </el-container>
  </el-container>

  <router-view v-else />
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useCurrentUserStore } from './stores/currentUser'

const route = useRoute()
const router = useRouter()
const collapsed = ref(false)
const userStore = useCurrentUserStore()

const showShell = computed(() => route.path !== '/login')
const activeMenu = computed(() => route.path)
const currentUserLabel = computed(() => userStore.label.value || '未登录')

onMounted(() => {
  userStore.ensureLoaded()
})

const routeTitle = computed(() => {
  const map: Record<string, string> = {
    '/chat': '聊天中心',
    '/knowledge-bases': '知识库管理',
    '/documents': '文档管理',
    '/settings/models': '模型设置',
  }
  return map[route.path] || '首页'
})

const logout = () => {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  userStore.clearProfile()
  router.push('/login')
}
</script>

<style scoped>
:global(html),
:global(body),
:global(#app) {
  width: 100%;
  height: 100%;
  margin: 0;
  overflow: hidden;
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: linear-gradient(90deg, #111827 0%, #1f2937 100%);
  color: #fff;
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.12);
}
.brand {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.5px;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
.app-aside {
  background: #fff;
  border-right: 1px solid #ebeef5;
}
.aside-toolbar {
  padding: 12px;
  border-bottom: 1px solid #f1f5f9;
}
.sidebar-menu {
  border-right: none;
}
.app-main {
  background: #f5f7fa;
  overflow: hidden;
  min-height: 0;
}
.breadcrumb-bar {
  margin-bottom: 16px;
  padding: 12px 16px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.06);
}
</style>
