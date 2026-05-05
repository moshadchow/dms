import { apiClient } from './client'
import type {
  Document,
  DocumentListResponse,
  DocumentUpdateRequest,
  DocumentListParams,
} from '@/types/document.types'

export const documentsApi = {
  list: async (params?: DocumentListParams): Promise<DocumentListResponse> => {
    const res = await apiClient.get<DocumentListResponse>('/documents', { params })
    return res.data
  },

  get: async (id: number): Promise<Document> => {
    const res = await apiClient.get<Document>(`/documents/${id}`)
    return res.data
  },

  upload: async (
    file: File,
    title: string,
    directoryId: number,
    description?: string
  ): Promise<Document> => {
    const form = new FormData()
    form.append('file', file)
    form.append('title', title)
    form.append('directory_id', String(directoryId))
    if (description) form.append('description', description)

    const res = await apiClient.post<Document>('/documents/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return res.data
  },

  update: async (id: number, data: DocumentUpdateRequest): Promise<Document> => {
    const res = await apiClient.patch<Document>(`/documents/${id}`, data)
    return res.data
  },

  delete: async (id: number, hard = false): Promise<void> => {
    await apiClient.delete(`/documents/${id}`, { params: { hard } })
  },

  archive: async (id: number): Promise<Document> => {
    const res = await apiClient.post<Document>(`/documents/${id}/archive`)
    return res.data
  },

  restore: async (id: number): Promise<Document> => {
    const res = await apiClient.post<Document>(`/documents/${id}/restore`)
    return res.data
  },

  // Returns a blob URL for inline preview or download
  getViewUrl: (id: number): string => {
    const token = localStorage.getItem('access_token')
    const base = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'
    return `${base}/api/v1/documents/${id}/view?token=${token}`
  },

  download: async (id: number, fileName: string): Promise<void> => {
    const res = await apiClient.get(`/documents/${id}/download`, {
      responseType: 'blob',
    })
    const url = URL.createObjectURL(res.data as Blob)
    const a = document.createElement('a')
    a.href = url
    a.download = fileName
    a.click()
    URL.revokeObjectURL(url)
  },
}
