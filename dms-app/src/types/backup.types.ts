// Backup types (spec 35) — mirrors backend backups/models.py read schemas

export type BackupStatus = 'pending' | 'running' | 'success' | 'failed'
export type BackupTrigger = 'manual' | 'scheduled'

export interface BackupRun {
  id: number
  company_id: number
  company_short_name: string | null
  status: BackupStatus
  trigger: BackupTrigger
  triggered_by: number | null
  triggered_by_name: string | null
  started_at: string | null
  finished_at: string | null
  file_count: number
  total_bytes: number
  // POSIX path relative to BACKUP_ROOT; null = pruned by retention policy
  archive_path: string | null
  archive_size_bytes: number | null
  error_message: string | null
  created_at: string
}

export interface BackupRunListResponse {
  total: number
  page: number
  limit: number
  items: BackupRun[]
  next_page: number | null
  prev_page: number | null
}

export interface BackupSettings {
  enabled: boolean
  interval_hours: number
  retention_count: number
}

export interface BackupSettingsUpdate {
  enabled: boolean
  interval_hours: number
  retention_count: number
}
