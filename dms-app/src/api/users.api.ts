import { apiClient } from './client'
import type {
  User,
  UserListResponse,
  UserCreateRequest,
  UserUpdateRequest,
  Role,
  Permission,
  RoleCreateRequest,
  UserLevel,
  UserLevelCreateRequest,
  UserLevelUpdateRequest,
} from '@/types/user.types'

export const usersApi = {
  // ── Users ────────────────────────────────────────────────────────
  list: async (params?: {
    skip?: number
    limit?: number
    search?: string
    is_active?: boolean
    user_level_id?: number | null
  }): Promise<UserListResponse> => {
    const res = await apiClient.get<UserListResponse>('/users', { params })
    return res.data
  },

  get: async (id: number): Promise<User> => {
    const res = await apiClient.get<User>(`/users/${id}`)
    return res.data
  },

  create: async (data: UserCreateRequest): Promise<User> => {
    const res = await apiClient.post<User>('/users', data)
    return res.data
  },

  update: async (id: number, data: UserUpdateRequest): Promise<User> => {
    const res = await apiClient.patch<User>(`/users/${id}`, data)
    return res.data
  },

  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/users/${id}`)
  },

  deactivate: async (id: number): Promise<User> => {
    const res = await apiClient.post<User>(`/users/${id}/deactivate`)
    return res.data
  },

  // ── Roles ─────────────────────────────────────────────────────────
  listRoles: async (): Promise<Role[]> => {
    const res = await apiClient.get<Role[]>('/users/roles/all')
    return res.data
  },

  getRole: async (id: number): Promise<Role> => {
    const res = await apiClient.get<Role>(`/users/roles/${id}`)
    return res.data
  },

  createRole: async (data: RoleCreateRequest): Promise<Role> => {
    const res = await apiClient.post<Role>('/users/roles', data)
    return res.data
  },

  // ── Permissions ───────────────────────────────────────────────────
  listPermissions: async (): Promise<Permission[]> => {
    const res = await apiClient.get<Permission[]>('/users/permissions/all')
    return res.data
  },

  // ── User Levels ───────────────────────────────────────────────────
  listUserLevels: async (): Promise<UserLevel[]> => {
    const res = await apiClient.get<UserLevel[]>('/user-levels')
    return res.data
  },

  listActiveUserLevels: async (): Promise<UserLevel[]> => {
    const res = await apiClient.get<UserLevel[]>('/user-levels/active')
    return res.data
  },

  getUserLevel: async (id: number): Promise<UserLevel> => {
    const res = await apiClient.get<UserLevel>(`/user-levels/${id}`)
    return res.data
  },

  createUserLevel: async (data: UserLevelCreateRequest): Promise<UserLevel> => {
    const res = await apiClient.post<UserLevel>('/user-levels', data)
    return res.data
  },

  updateUserLevel: async (id: number, data: UserLevelUpdateRequest): Promise<UserLevel> => {
    const res = await apiClient.patch<UserLevel>(`/user-levels/${id}`, data)
    return res.data
  },

  deleteUserLevel: async (id: number): Promise<void> => {
    await apiClient.delete(`/user-levels/${id}`)
  },
}
