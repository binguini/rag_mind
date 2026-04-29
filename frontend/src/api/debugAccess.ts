import { apiClient } from './client'

export interface DebugAccessPolicyResponse {
  enabled: boolean
  allowed_user_ids: number[]
  can_access: boolean
  can_manage: boolean
}

export interface DebugAccessPolicyUpdate {
  enabled: boolean
  allowed_user_ids: number[]
}

export const getDebugAccessPolicy = async () => {
  const { data } = await apiClient.get<DebugAccessPolicyResponse>('/admin/debug-access')
  return data
}

export const updateDebugAccessPolicy = async (payload: DebugAccessPolicyUpdate) => {
  const { data } = await apiClient.put<DebugAccessPolicyResponse>('/admin/debug-access', payload)
  return data
}
