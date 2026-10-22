// Database backup types (spec 36) — mirrors backend db_backups/models.py read schemas.
//
// NOTE: unlike BackupRun there is no company_id / company_short_name anywhere
// in this shape. One pg_dump holds every company's rows, so the resource is
// deployment-scoped and every endpoint is SuperAdmin-only.

export type DbBackupStatus = 'pending' | 'running' | 'success' | 'failed'
export type DbBackupTrigger = 'manual' | 'scheduled'

export interface DbBackupRun {
  id: number
  status: DbBackupStatus
  trigger: DbBackupTrigger
  triggered_by: number | null
  triggered_by_name: string | null
  started_at: string | null
  finished_at: string | null
  // POSIX path relative to DB_BACKUP_ROOT; null = pruned by retention policy
  dump_path: string | null
  dump_size_bytes: number | null
  duration_ms: number | null
  // `pg_dump --version` — which client produced the archive, which matters
  // when restoring into a different PostgreSQL major version later.
  pg_dump_version: string | null
  error_message: string | null
  created_at: string
}

export interface DbBackupRunListResponse {
  total: number
  page: number
  limit: number
  items: DbBackupRun[]
  next_page: number | null
  prev_page: number | null
}

export interface DbBackupSettings {
  enabled: boolean
  interval_hours: number
  retention_count: number
}

export type DbBackupSettingsUpdate = DbBackupSettings
