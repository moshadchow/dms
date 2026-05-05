import { apiClient } from './client'
import type { Category, CategoryCreateRequest, CategoryUpdateRequest } from '@/types/category.types'

export const categoriesApi = {
  list: async (includeInactive = false): Promise<Category[]> => {
    const res = await apiClient.get<Category[]>('/categories', {
      params: { include_inactive: includeInactive },
    })
    return res.data
  },

  get: async (id: number): Promise<Category> => {
    const res = await apiClient.get<Category>(`/categories/${id}`)
    return res.data
  },

  create: async (data: CategoryCreateRequest): Promise<Category> => {
    const res = await apiClient.post<Category>('/categories', data)
    return res.data
  },

  update: async (id: number, data: CategoryUpdateRequest): Promise<Category> => {
    const res = await apiClient.patch<Category>(`/categories/${id}`, data)
    return res.data
  },

  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/categories/${id}`)
  },
}
