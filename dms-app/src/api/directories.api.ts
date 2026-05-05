import { apiClient } from './client'
import type {
  Directory,
  DirectoryNode,
  DirectoryCreateRequest,
  DirectoryUpdateRequest,
} from '@/types/directory.types'

export const directoriesApi = {
  listByCategory: async (categoryId: number): Promise<Directory[]> => {
    const res = await apiClient.get<Directory[]>(`/directories/category/${categoryId}`)
    return res.data
  },

  getTree: async (categoryId: number): Promise<DirectoryNode[]> => {
    const res = await apiClient.get<DirectoryNode[]>(`/directories/category/${categoryId}/tree`)
    return res.data
  },

  get: async (id: number): Promise<Directory> => {
    const res = await apiClient.get<Directory>(`/directories/${id}`)
    return res.data
  },

  create: async (data: DirectoryCreateRequest): Promise<Directory> => {
    const res = await apiClient.post<Directory>('/directories', data)
    return res.data
  },

  update: async (id: number, data: DirectoryUpdateRequest): Promise<Directory> => {
    const res = await apiClient.patch<Directory>(`/directories/${id}`, data)
    return res.data
  },

  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/directories/${id}`)
  },
}
