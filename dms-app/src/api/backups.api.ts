import { apiClient } from './client'
import type {
  BackupRun,
  BackupRunListResponse,
  BackupSettings,
  BackupSettingsUpdate,
} from '@/types/backup.types'

export const backupsApi = {
  list: (params?: { company_id?: number; skip?: number; limit?: number }) =>
    apiClient.get<BackupRunListResponse>('/backups', { params }).then((r) => r.data),

  get: (id: number) => apiClient.get<BackupRun>(`/backups/${id}`).then((r) => r.data),

  runNow: () => apiClient.post<BackupRun>('/backups/run').then((r) => r.data),

  getSettings: () => apiClient.get<BackupSettings>('/backups/settings').then((r) => r.data),

  updateSettings: (payload: BackupSettingsUpdate) =>
    apiClient.put<BackupSettings>('/backups/settings', payload).then((r) => r.data),

  download: async (id: number, fileName: string): Promise<void> => {
    const res = await apiClient.get(`/backups/${id}/download`, {
      responseType: 'blob',
    })
    const blob = res.data as Blob
    if (blob.type === 'application/json') {
      const text = await blob.text()
      const json = JSON.parse(text)
      throw new Error(json.detail || 'Download failed')
    }
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = fileName
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  },
}
