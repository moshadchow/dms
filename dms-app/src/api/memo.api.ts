import { apiClient } from './client'
import type {
  MemoCreate,
  MemoDetail,
  MemoListResponse,
  MemoSubmit,
  MemoUpdate,
} from '@/types/memo.types'

export const memoApi = {
  list: async (params?: { skip?: number; limit?: number }): Promise<MemoListResponse> => {
    const res = await apiClient.get<MemoListResponse>('/memos', { params })
    return res.data
  },

  get: async (id: number): Promise<MemoDetail> => {
    const res = await apiClient.get<MemoDetail>(`/memos/${id}`)
    return res.data
  },

  getByDocument: async (documentId: number): Promise<MemoDetail> => {
    const res = await apiClient.get<MemoDetail>(`/memos/by-document/${documentId}`)
    return res.data
  },

  create: async (data: MemoCreate): Promise<MemoDetail> => {
    const res = await apiClient.post<MemoDetail>('/memos', data)
    return res.data
  },

  update: async (id: number, data: MemoUpdate): Promise<MemoDetail> => {
    const res = await apiClient.patch<MemoDetail>(`/memos/${id}`, data)
    return res.data
  },

  submit: async (id: number, data: MemoSubmit): Promise<MemoDetail> => {
    const res = await apiClient.post<MemoDetail>(`/memos/${id}/submit`, data)
    return res.data
  },

  downloadFinalDraft: async (id: number): Promise<Blob> => {
    const res = await apiClient.get(`/memos/${id}/download-final-draft`, {
      responseType: 'blob',
    })
    return res.data
  },
}
