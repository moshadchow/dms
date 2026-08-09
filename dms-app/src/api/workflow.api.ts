import { apiClient } from './client'
import type {
  WorkflowDefinition,
  WorkflowDefinitionCreate,
  WorkflowDefinitionDetail,
  WorkflowDefinitionListResponse,
  WorkflowDefinitionUpdate,
} from '@/types/workflow.types'

export const workflowApi = {
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
}
