import type { UserProfile } from '../api/users'

const PROFILE_CACHE_KEY = 'current_user_profile'

export const saveCurrentUserProfile = (profile: UserProfile) => {
  localStorage.setItem(PROFILE_CACHE_KEY, JSON.stringify(profile))
}

export const getCurrentUserProfile = (): UserProfile | null => {
  const raw = localStorage.getItem(PROFILE_CACHE_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as UserProfile
  } catch {
    return null
  }
}

export const getCurrentUserLabel = () => {
  const profile = getCurrentUserProfile()
  if (profile?.nickname?.trim()) return `当前用户：${profile.nickname.trim()}`
  if (profile?.username?.trim()) return `当前用户：${profile.username.trim()}`

  const token = localStorage.getItem('access_token')
  if (!token) return '未登录'

  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return payload?.sub ? `当前用户：${payload.sub}` : '已登录'
  } catch {
    return '已登录'
  }
}
