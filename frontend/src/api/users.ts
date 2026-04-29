import { apiClient } from './client'

export interface UserProfile {
  id: number
  username: string
  avatar_url: string | null
  nickname: string | null
  signature: string | null
  debug_access_enabled: boolean
}

export interface UserProfileUpdatePayload {
  avatar_url: string | null
  nickname: string | null
  signature: string | null
}

export const getCurrentUser = async (): Promise<UserProfile> => {
  const { data } = await apiClient.get('/auth/me')
  return data
}

export const updateCurrentUser = async (payload: UserProfileUpdatePayload): Promise<UserProfile> => {
  const { data } = await apiClient.put('/auth/me', payload)
  return data
}
