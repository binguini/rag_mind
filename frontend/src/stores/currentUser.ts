import { computed, ref } from 'vue'
import type { UserProfile } from '../api/users'
import { getCurrentUser, updateCurrentUser } from '../api/users'

const PROFILE_CACHE_KEY = 'current_user_profile'
const currentUser = ref<UserProfile | null>(null)
const loaded = ref(false)

const readCachedProfile = (): UserProfile | null => {
  const raw = localStorage.getItem(PROFILE_CACHE_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as UserProfile
  } catch {
    return null
  }
}

const persistProfile = (profile: UserProfile | null) => {
  if (!profile) {
    localStorage.removeItem(PROFILE_CACHE_KEY)
    currentUser.value = null
    loaded.value = false
    return
  }
  currentUser.value = profile
  localStorage.setItem(PROFILE_CACHE_KEY, JSON.stringify(profile))
}

const ensureLoaded = async () => {
  if (loaded.value) return currentUser.value
  const cached = readCachedProfile()
  if (cached) {
    currentUser.value = cached
  }
  loaded.value = true
  if (!currentUser.value && localStorage.getItem('access_token')) {
    try {
      const profile = await getCurrentUser()
      persistProfile(profile)
    } catch {
      // ignore and keep fallback label
    }
  }
  return currentUser.value
}

export const useCurrentUserStore = () => {
  const label = computed(() => {
    const profile = currentUser.value
    if (profile?.nickname?.trim()) return profile.nickname.trim()
    if (profile?.username?.trim()) return profile.username.trim()
    return ''
  })

  return {
    currentUser,
    label,
    loaded,
    ensureLoaded,
    setProfile: persistProfile,
    clearProfile: () => persistProfile(null),
    updateProfile: async (payload: Parameters<typeof updateCurrentUser>[0]) => {
      const profile = await updateCurrentUser(payload)
      persistProfile(profile)
      return profile
    },
  }
}
