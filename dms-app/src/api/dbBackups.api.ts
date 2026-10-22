import { apiClient } from './client'
import type {
  DbBackupRun,
  DbBackupRunListResponse,
  DbBackupSettings,
  DbBackupSettingsUpdate,
} from '@/types/dbBackup.types'

// Every endpoint here is SuperAdmin-only on the backend (a dump spans all
// companies). Keep that gate in the page/nav too — do not "fix" a 403 by
// catching it here.

export const dbBackupsApi = {
  list: (params?: { skip?: number; limit?: number }) =>
    apiClient.get<DbBackupRunListResponse>('/db-backups', { params }).then((r) => r.data),

  get: (id: number) => apiClient.get<DbBackupRun>(`/db-backups/${id}`).then((r) => r.data),

  // A failure comes back as HTTP 200 with status: "failed" — it is data, not
  // an error response. Callers must branch on run.status.
  runNow: () => apiClient.post<DbBackupRun>('/db-backups/run').then((r) => r.data),

  getSettings: () => apiClient.get<DbBackupSettings>('/db-backups/settings').then((r) => r.data),

  updateSettings: (payload: DbBackupSettingsUpdate) =>
    apiClient.put<DbBackupSettings>('/db-backups/settings', payload).then((r) => r.data),

  // A 4xx/5xx rejects with an AxiosError whose body the response interceptor
  // has already converted from Blob back into JSON (see api/client.ts), so
  // callers simply use getErrorMessage(err) — do not re-parse the Blob here.
  download: async (id: number, fileName: string): Promise<void> => {
    const res = await apiClient.get(`/db-backups/${id}/download`, {
      responseType: 'blob',
    })
    const blob = res.data as Blob
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
