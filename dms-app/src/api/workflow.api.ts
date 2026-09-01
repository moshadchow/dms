import { apiClient } from './client'
import type {
  Signature,
  SignatureType,
  WorkflowActionCreate,
  WorkflowDefinition,
  WorkflowDefinitionCreate,
  WorkflowDefinitionDetail,
  WorkflowDefinitionListResponse,
  WorkflowDefinitionUpdate,
  WorkflowInstance,
  WorkflowInstanceDetail,
  WorkflowInstanceListResponse,
} from '@/types/workflow.types'

export const workflowApi = {
  // ── Definitions ─────────────────────────────────

  list: async (params?: {
    category_id?: number
    is_active?: boolean
    skip?: number
    limit?: number
  }): Promise<WorkflowDefinitionListResponse> => {
    const res = await apiClient.get<WorkflowDefinitionListResponse>('/workflows', { params })
    return res.data
  },

  get: async (id: number): Promise<WorkflowDefinitionDetail> => {
    const res = await apiClient.get<WorkflowDefinitionDetail>(`/workflows/${id}`)
    return res.data
  },

  create: async (data: WorkflowDefinitionCreate): Promise<WorkflowDefinition> => {
    const res = await apiClient.post<WorkflowDefinition>('/workflows', data)
    return res.data
  },

  update: async (id: number, data: WorkflowDefinitionUpdate): Promise<WorkflowDefinition> => {
    const res = await apiClient.put<WorkflowDefinition>(`/workflows/${id}`, data)
    return res.data
  },

  deactivate: async (id: number): Promise<WorkflowDefinition> => {
    const res = await apiClient.delete<WorkflowDefinition>(`/workflows/${id}`)
    return res.data
  },

  activate: async (id: number): Promise<WorkflowDefinition> => {
    const res = await apiClient.patch<WorkflowDefinition>(`/workflows/${id}/activate`)
    return res.data
  },

  // ── Instances ───────────────────────────────────

  submitInstance: async (data: {
    document_id: number
    workflow_definition_id: number
  }): Promise<WorkflowInstance> => {
    const res = await apiClient.post<WorkflowInstance>('/workflow-instances', data)
    return res.data
  },

  getInstances: async (params?: {
    skip?: number
    limit?: number
  }): Promise<WorkflowInstanceListResponse> => {
    const res = await apiClient.get<WorkflowInstanceListResponse>('/workflow-instances', { params })
    return res.data
  },

  getPendingInstances: async (params?: {
    skip?: number
    limit?: number
  }): Promise<WorkflowInstanceListResponse> => {
    const res = await apiClient.get<WorkflowInstanceListResponse>('/workflow-instances/pending', { params })
    return res.data
  },

  getMyInstances: async (params?: {
    skip?: number
    limit?: number
  }): Promise<WorkflowInstanceListResponse> => {
    const res = await apiClient.get<WorkflowInstanceListResponse>('/workflow-instances/mine', { params })
    return res.data
  },

  getInstance: async (id: number): Promise<WorkflowInstanceDetail> => {
    const res = await apiClient.get<WorkflowInstanceDetail>(`/workflow-instances/${id}`)
    return res.data
  },

  getInstanceByDocument: async (documentId: number): Promise<WorkflowInstanceDetail> => {
    const res = await apiClient.get<WorkflowInstanceDetail>(`/workflow-instances/by-document/${documentId}`)
    return res.data
  },

  actOnInstance: async (id: number, data: WorkflowActionCreate): Promise<WorkflowInstance> => {
    const res = await apiClient.post<WorkflowInstance>(`/workflow-instances/${id}/actions`, data)
    return res.data
  },

  cancelInstance: async (id: number): Promise<WorkflowInstance> => {
    const res = await apiClient.post<WorkflowInstance>(`/workflow-instances/${id}/cancel`)
    return res.data
  },

  // ── Signatures ──────────────────────────────────

  listSignatures: async (): Promise<Signature[]> => {
    const res = await apiClient.get<Signature[]>('/signatures')
    return res.data
  },

  uploadSignature: async (
    file: File,
    sigType: SignatureType
  ): Promise<Signature> => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('sig_type', sigType)
    const res = await apiClient.post<Signature>('/signatures', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return res.data
  },

  getSignature: async (id: number): Promise<Signature> => {
    const res = await apiClient.get<Signature>(`/signatures/${id}`)
    return res.data
  },

  deleteSignature: async (id: number): Promise<Signature> => {
    const res = await apiClient.delete<Signature>(`/signatures/${id}`)
    return res.data
  },

  getSignatureFileUrl: async (id: number): Promise<string> => {
    const res = await apiClient.get(`/signatures/${id}/file`, { responseType: 'blob' })
    return URL.createObjectURL(res.data as Blob)
  },

  // ── Admin Signature Management ─────────────────

  adminListSignaturesForUser: async (userId: number): Promise<Signature[]> => {
    const res = await apiClient.get<Signature[]>(`/signatures/admin/${userId}`)
    return res.data
  },

  adminUploadSignatureForUser: async (
    userId: number,
    file: File,
    sigType: SignatureType
  ): Promise<Signature> => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('sig_type', sigType)
    const res = await apiClient.post<Signature>(`/signatures/admin/${userId}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return res.data
  },

  adminDeleteSignatureForUser: async (
    userId: number,
    signatureId: number
  ): Promise<Signature> => {
    const res = await apiClient.delete<Signature>(`/signatures/admin/${userId}/${signatureId}`)
    return res.data
  },
}
