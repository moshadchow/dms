import { apiClient } from './client'
import type { AuditLogListResponse, AuditLog, AuditLogFilters } from '@/types/audit.types'

export const auditApi = {
  async list(filters: AuditLogFilters = {}): Promise<AuditLogListResponse> {
    const params: Record<string, string> = {}
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        params[key] = String(value)
      }
    })
    const { data } = await apiClient.get<AuditLogListResponse>('/audit-logs', { params })
    return data
  },

  async get(id: number): Promise<AuditLog> {
    const { data } = await apiClient.get<AuditLog>(`/audit-logs/${id}`)
    return data
  },

  async export(filters: AuditLogFilters = {}, format: 'csv' | 'excel' = 'csv'): Promise<Blob> {
    const params: Record<string, string> = { format }
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        params[key] = String(value)
      }
    })
    const { data } = await apiClient.get('/audit-logs/export', {
      params,
      responseType: 'blob',
    })
    return data
  },
}
