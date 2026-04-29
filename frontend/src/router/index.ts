import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '../views/LoginView.vue'
import KnowledgeBaseView from '../views/KnowledgeBaseView.vue'
import DocumentUploadView from '../views/DocumentUploadView.vue'
import ChatCenterView from '../views/ChatCenterView.vue'
import ModelSettingsView from '../views/ModelSettingsView.vue'
import RAGDebugView from '../views/RAGDebugView.vue'
import UserSettingsView from '../views/UserSettingsView.vue'

const isAuthenticated = () => Boolean(localStorage.getItem('access_token'))

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/login' },
    { path: '/login', component: LoginView },
    { path: '/chat', component: ChatCenterView },
    { path: '/chat/general', redirect: '/chat' },
    { path: '/chat/rag', redirect: '/chat' },
    { path: '/general-chat', redirect: '/chat' },
    { path: '/rag-chat', redirect: '/chat' },
    { path: '/knowledge-bases', component: KnowledgeBaseView },
    { path: '/documents', component: DocumentUploadView },
    { path: '/settings/models', component: ModelSettingsView },
    { path: '/rag-debug', component: RAGDebugView },
    { path: '/settings/user', component: UserSettingsView },
  ],
})

router.beforeEach((to) => {
  if (to.path !== '/login' && !isAuthenticated()) {
    return '/login'
  }
  if (to.path === '/login' && isAuthenticated()) {
    return '/chat'
  }
  return true
})
