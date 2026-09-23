import { apiClient } from './client'
import type {
  CorrespondenceAttachment,
  CorrespondenceAssign,
  CorrespondenceCreate,
  CorrespondenceDetail,
  CorrespondenceDispatch,
  CorrespondenceListResponse,
  CorrespondenceSubmit,
  CorrespondenceUpdate,
  NextReferenceResponse,
} from '@/types/correspondence.types'

export interface CorrespondenceListParams {
  skip?: number
  limit?: number
  direction?: string
  priority?: string
  status?: string
  category_id?: number
  response_required?: boolean
  overdue?: boolean
  search?: string
  date_from?: string
  date_to?: string
}

export const correspondenceApi = {
  list: async (params?: CorrespondenceListParams): Promise<CorrespondenceListResponse> => {
    const res = await apiClient.get<CorrespondenceListResponse>('/correspondences', { params })
    return res.data
  },

  get: async (id: number): Promise<CorrespondenceDetail> => {
    const res = await apiClient.get<CorrespondenceDetail>(`/correspondences/${id}`)
    return res.data
  },

  create: async (data: CorrespondenceCreate): Promise<CorrespondenceDetail> => {
    const res = await apiClient.post<CorrespondenceDetail>('/correspondences', data)
    return res.data
  },

  update: async (id: number, data: CorrespondenceUpdate): Promise<CorrespondenceDetail> => {
    const res = await apiClient.patch<CorrespondenceDetail>(`/correspondences/${id}`, data)
    return res.data
  },

  submit: async (id: number, data: CorrespondenceSubmit): Promise<CorrespondenceDetail> => {
    const res = await apiClient.post<CorrespondenceDetail>(`/correspondences/${id}/submit`, data)
    return res.data
  },

  assign: async (id: number, data: CorrespondenceAssign): Promise<CorrespondenceDetail> => {
    const res = await apiClient.post<CorrespondenceDetail>(`/correspondences/${id}/assign`, data)
    return res.data
  },

  forward: async (id: number, data: CorrespondenceAssign): Promise<CorrespondenceDetail> => {
    const res = await apiClient.post<CorrespondenceDetail>(`/correspondences/${id}/forward`, data)
    return res.data
  },

  dispatch: async (id: number, data: CorrespondenceDispatch): Promise<CorrespondenceDetail> => {
    const res = await apiClient.post<CorrespondenceDetail>(`/correspondences/${id}/dispatch`, data)
    return res.data
  },

  deliver: async (id: number): Promise<CorrespondenceDetail> => {
    const res = await apiClient.post<CorrespondenceDetail>(`/correspondences/${id}/deliver`)
    return res.data
  },

  acknowledge: async (id: number): Promise<CorrespondenceDetail> => {
    const res = await apiClient.post<CorrespondenceDetail>(`/correspondences/${id}/acknowledge`)
    return res.data
  },

  getNextReference: async (): Promise<NextReferenceResponse> => {
    const res = await apiClient.get<NextReferenceResponse>('/correspondences/next-reference')
    return res.data
  },

  download: async (id: number): Promise<Blob> => {
    const res = await apiClient.get(`/correspondences/${id}/download`, { responseType: 'blob' })
    return res.data
  },

  downloadFinal: async (id: number): Promise<Blob> => {
    const res = await apiClient.get(`/correspondences/${id}/download-final`, { responseType: 'blob' })
    return res.data
  },

  complete: async (id: number, remarks?: string): Promise<CorrespondenceDetail> => {
    const res = await apiClient.post<CorrespondenceDetail>(`/correspondences/${id}/complete`, { remarks })
    return res.data
  },

  archive: async (id: number, remarks?: string): Promise<CorrespondenceDetail> => {
    const res = await apiClient.post<CorrespondenceDetail>(`/correspondences/${id}/archive`, { remarks })
    return res.data
  },

  actOnWorkflowInstance: async (instanceId: number, action: 'approve' | 'reject' | 'return' | 'clarify' | 'forward', remarks?: string): Promise<unknown> => {
    const res = await apiClient.post(`/workflow-instances/${instanceId}/actions`, { action, remarks })
    return res.data
  },

  addAttachment: async (id: number, file: File, attachmentType: string = 'supporting'): Promise<CorrespondenceAttachment> => {
    const form = new FormData()
    form.append('file', file)
    form.append('attachment_type', attachmentType)
    const res = await apiClient.post<CorrespondenceAttachment>(`/correspondences/${id}/attachments`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return res.data
  },

  removeAttachment: async (correspondenceId: number, attachmentId: number): Promise<void> => {
    await apiClient.delete(`/correspondences/${correspondenceId}/attachments/${attachmentId}`)
  },

  getByDocument: async (documentId: number): Promise<CorrespondenceDetail> => {
    const res = await apiClient.get<CorrespondenceDetail>(`/correspondences/by-document/${documentId}`)
    return res.data
  },

  createReply: async (parentId: number, data: CorrespondenceCreate): Promise<CorrespondenceDetail> => {
    const res = await apiClient.post<CorrespondenceDetail>(`/correspondences/${parentId}/reply`, data)
    return res.data
  },

  getReplies: async (parentId: number): Promise<CorrespondenceDetail[]> => {
    const res = await apiClient.get<CorrespondenceDetail[]>(`/correspondences/${parentId}/replies`)
    return res.data
  },

  submitReply: async (id: number, data: CorrespondenceSubmit): Promise<CorrespondenceDetail> => {
    const res = await apiClient.post<CorrespondenceDetail>(`/correspondences/${id}/submit-reply`, data)
    return res.data
  },

  markResponded: async (id: number): Promise<CorrespondenceDetail> => {
    const res = await apiClient.post<CorrespondenceDetail>(`/correspondences/${id}/mark-responded`)
    return res.data
  },

  downloadAttachment: async (correspondenceId: number, attachmentId: number): Promise<Blob> => {
    const res = await apiClient.get(`/correspondences/${correspondenceId}/attachments/${attachmentId}/download`, { responseType: 'blob' })
    return res.data
  },
}
