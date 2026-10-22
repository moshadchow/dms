import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'react-hot-toast'
import { dbBackupsApi } from '@/api/dbBackups.api'
import { useAuthStore } from '@/store/authStore'
import { getErrorMessage } from '@/api/client'
import type {
  DbBackupRun,
  DbBackupSettings,
  DbBackupStatus,
  DbBackupTrigger,
} from '@/types/dbBackup.types'

const LIMIT = 50

const STATUS_META: Record<DbBackupStatus, { label: string; color: string; bg: string }> = {
  success: { label: 'Success', color: '#16a34a', bg: 'rgba(22, 163, 74, 0.12)' },
  failed:  { label: 'Failed',  color: '#dc2626', bg: 'rgba(220, 38, 38, 0.12)' },
  running: { label: 'Running', color: '#2563eb', bg: 'rgba(37, 99, 235, 0.12)' },
  pending: { label: 'Pending', color: '#d97706', bg: 'rgba(217, 119, 6, 0.12)' },
}

function formatBytes(bytes: number | null): string {
  if (bytes === null || bytes === undefined) return '—'
  if (bytes < 1024) return `${bytes} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let value = bytes
  let unit = 'B'
  for (const u of units) {
    if (value < 1024) break
    value /= 1024
    unit = u
  }
  return `${value.toFixed(1)} ${unit}`
}

function formatDateTime(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString()
}

function formatDuration(ms: number | null): string {
  if (ms === null || ms === undefined) return '—'
  if (ms < 1000) return `${ms} ms`
  const totalSeconds = ms / 1000
  if (totalSeconds < 60) return `${totalSeconds.toFixed(1)} s`
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = Math.round(totalSeconds % 60)
  if (minutes < 60) return `${minutes}m ${seconds}s`
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`
}

/** "pg_dump (PostgreSQL) 18.3" → "18.3", full text kept in the tooltip. */
function shortVersion(version: string | null): string {
  if (!version) return '—'
  const match = version.match(/(\d+(?:\.\d+)+)$/)
  return match ? match[1] : version
}

function StatusBadge({ status }: { status: DbBackupStatus }) {
  const meta = STATUS_META[status]
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '5px',
      padding: '2px 10px', borderRadius: '999px', fontSize: '0.72rem',
      fontWeight: 700, color: meta.color, backgroundColor: meta.bg,
    }}>
      <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: meta.color }} />
      {meta.label}
    </span>
  )
}

function TriggerBadge({ trigger }: { trigger: DbBackupTrigger }) {
  return (
    <span style={{
      padding: '2px 8px', borderRadius: '6px', fontSize: '0.72rem', fontWeight: 600,
      color: 'var(--text-secondary)', backgroundColor: 'var(--surface-2)',
    }}>
      {trigger === 'manual' ? 'Manual' : 'Scheduled'}
    </span>
  )
}

const TH: React.CSSProperties = { padding: '10px 14px', fontWeight: 600 }
const TD: React.CSSProperties = { padding: '10px 14px' }

export default function DbBackupsPage() {
  const navigate = useNavigate()
  const isSuperAdmin = useAuthStore((s) => s.isSuperAdmin())

  // Deployment-scoped resource: only a Super Admin may see any of it.
  // ProtectedRoute has already resolved the user by the time this renders.
  // `isSuperAdmin` here is the BOOLEAN from the selector (same convention as
  // BackupsPage/AuditTrailPage) — do not call it as a function.
  useEffect(() => {
    if (!isSuperAdmin) {
      navigate('/dashboard', { replace: true })
    }
  }, [isSuperAdmin, navigate])

  const [runs, setRuns] = useState<DbBackupRun[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [runningNow, setRunningNow] = useState(false)

  const [settings, setSettings] = useState<DbBackupSettings | null>(null)
  const [savingSettings, setSavingSettings] = useState(false)

  const loadRuns = useCallback(() => {
    Promise.resolve()
      .then(() => {
        setLoading(true)
        return dbBackupsApi.list({ skip: (page - 1) * LIMIT, limit: LIMIT })
      })
      .then((data) => {
        setRuns(data.items)
        setTotal(data.total)
      })
      .catch((err) => toast.error(getErrorMessage(err)))
      .finally(() => setLoading(false))
  }, [page])

  useEffect(() => { loadRuns() }, [loadRuns])

  useEffect(() => {
    dbBackupsApi.getSettings()
      .then(setSettings)
      .catch((err) => toast.error(getErrorMessage(err)))
  }, [])

  const handleRunNow = () => {
    setRunningNow(true)
    dbBackupsApi.runNow()
      .then((run) => {
        // Failure is data, not an error response — branch on status.
        if (run.status === 'success') {
          toast.success(`Database dump completed — ${formatBytes(run.dump_size_bytes)}`)
        } else {
          toast.error(run.error_message || 'Database dump failed')
        }
        loadRuns()
      })
      .catch((err) => toast.error(getErrorMessage(err)))
      .finally(() => setRunningNow(false))
  }

  const handleSaveSettings = () => {
    if (!settings) return
    setSavingSettings(true)
    dbBackupsApi.updateSettings({
      enabled: settings.enabled,
      interval_hours: settings.interval_hours,
      retention_count: settings.retention_count,
    })
      .then((updated) => {
        setSettings(updated)
        toast.success('Database backup settings saved')
      })
      .catch((err) => toast.error(getErrorMessage(err)))
      .finally(() => setSavingSettings(false))
  }

  const handleDownload = (run: DbBackupRun) => {
    if (!run.dump_path) return
    const fileName = run.dump_path.split('/').pop() || 'database.dump'
    dbBackupsApi.download(run.id, fileName)
      .then(() => toast.success('Database dump downloaded'))
      .catch((err) => toast.error(getErrorMessage(err)))
  }

  const totalPages = Math.ceil(total / LIMIT) || 1
  const dumpInProgress = runningNow || runs.some((r) => r.status === 'running')

  return (
    <div>
      {/* Page header */}
      <div style={{
        backgroundColor: 'var(--surface)', borderRadius: '1rem', border: '1px solid var(--border)',
        padding: '1.25rem 1.5rem', marginBottom: '1.25rem',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem',
      }}>
        <div>
          <h1 style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text)', margin: 0 }}>
            Database Backups
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.82rem', margin: '3px 0 0' }}>
            PostgreSQL dump service (pg_dump) · deployment-wide
          </p>
        </div>
        <button
          onClick={handleRunNow}
          disabled={dumpInProgress}
          style={{
            display: 'flex', alignItems: 'center', gap: '6px',
            padding: '7px 14px', backgroundColor: 'var(--text)', color: 'var(--surface)',
            border: 'none', borderRadius: '8px', fontSize: '0.85rem',
            fontWeight: 600, cursor: dumpInProgress ? 'not-allowed' : 'pointer',
            fontFamily: 'inherit', opacity: dumpInProgress ? 0.7 : 1,
          }}
        >
          {dumpInProgress ? 'Dumping…' : 'Dump database now'}
        </button>
      </div>

      {/* Scope notice — the user is about to handle every tenant's data */}
      <div style={{
        display: 'flex', alignItems: 'flex-start', gap: '10px',
        backgroundColor: 'rgba(217, 119, 6, 0.08)', border: '1px solid rgba(217, 119, 6, 0.35)',
        borderRadius: '0.75rem', padding: '0.75rem 1rem', marginBottom: '1.25rem',
      }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#d97706"
          strokeWidth="2" style={{ flexShrink: 0, marginTop: '1px' }}>
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
        </svg>
        <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
          <strong style={{ color: 'var(--text)' }}>Deployment-wide data.</strong>{' '}
          Each dump is a full copy of the database and contains every company&apos;s records
          in one file. There is no per-company scoping and no company filter on this page —
          handle archives accordingly.
        </p>
      </div>

      {/* Settings card */}
      {settings && (
        <div style={{
          backgroundColor: 'var(--surface)', borderRadius: '1rem', border: '1px solid var(--border)',
          padding: '1.25rem 1.5rem', marginBottom: '1.25rem',
        }}>
          <h2 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text)', margin: '0 0 0.9rem' }}>
            Schedule settings
          </h2>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: '1.25rem', flexWrap: 'wrap' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.85rem', color: 'var(--text)', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={settings.enabled}
                onChange={(e) => setSettings({ ...settings, enabled: e.target.checked })}
              />
              Automatic dumps enabled
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
              Interval (hours, 1–168)
              <input
                type="number"
                min={1}
                max={168}
                value={settings.interval_hours}
                onChange={(e) => setSettings({ ...settings, interval_hours: Number(e.target.value) })}
                style={{
                  padding: '6px 10px', border: '1px solid var(--border)', borderRadius: '8px',
                  fontSize: '0.85rem', width: '110px', backgroundColor: 'var(--surface)', color: 'var(--text)', fontFamily: 'inherit',
                }}
              />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
              Dump files kept (1–100)
              <input
                type="number"
                min={1}
                max={100}
                value={settings.retention_count}
                onChange={(e) => setSettings({ ...settings, retention_count: Number(e.target.value) })}
                style={{
                  padding: '6px 10px', border: '1px solid var(--border)', borderRadius: '8px',
                  fontSize: '0.85rem', width: '110px', backgroundColor: 'var(--surface)', color: 'var(--text)', fontFamily: 'inherit',
                }}
              />
            </label>
            <button
              onClick={handleSaveSettings}
              disabled={savingSettings}
              style={{
                padding: '7px 16px', backgroundColor: 'var(--primary)', color: '#fff',
                border: 'none', borderRadius: '8px', fontSize: '0.85rem',
                fontWeight: 600, cursor: savingSettings ? 'not-allowed' : 'pointer', fontFamily: 'inherit',
                opacity: savingSettings ? 0.7 : 1,
              }}
            >
              {savingSettings ? 'Saving…' : 'Save settings'}
            </button>
          </div>
        </div>
      )}

      {/* Runs table */}
      <div style={{
        backgroundColor: 'var(--surface)', borderRadius: '1rem', border: '1px solid var(--border)',
        overflow: 'hidden',
      }}>
        {loading ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-tertiary)', fontSize: '0.85rem' }}>
            Loading database backups…
          </div>
        ) : runs.length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-tertiary)', fontSize: '0.85rem' }}>
            No database backups yet — click “Dump database now” to create the first one.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-tertiary)', textAlign: 'left' }}>
                  <th style={TH}>Status</th>
                  <th style={TH}>Trigger</th>
                  <th style={TH}>Triggered by</th>
                  <th style={TH}>Started</th>
                  <th style={TH}>Finished</th>
                  <th style={TH}>Duration</th>
                  <th style={TH}>Size</th>
                  <th style={TH}>pg_dump</th>
                  <th style={TH} />
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.id} style={{ borderBottom: '1px solid var(--border)', color: 'var(--text)' }}>
                    <td style={TD}>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                        <StatusBadge status={run.status} />
                        {run.error_message && (
                          <span style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', maxWidth: '220px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={run.error_message}>
                            {run.error_message}
                          </span>
                        )}
                      </div>
                    </td>
                    <td style={TD}><TriggerBadge trigger={run.trigger} /></td>
                    <td style={TD}>{run.triggered_by_name ?? '—'}</td>
                    <td style={TD}>{formatDateTime(run.started_at)}</td>
                    <td style={TD}>{formatDateTime(run.finished_at)}</td>
                    <td style={TD}>{formatDuration(run.duration_ms)}</td>
                    <td style={TD}>
                      {run.dump_path ? formatBytes(run.dump_size_bytes) : 'Pruned'}
                    </td>
                    <td style={TD}>
                      <span title={run.pg_dump_version ?? undefined}>
                        {shortVersion(run.pg_dump_version)}
                      </span>
                    </td>
                    <td style={TD}>
                      {run.dump_path && (
                        <button
                          onClick={() => handleDownload(run)}
                          style={{
                            padding: '5px 12px', backgroundColor: 'var(--surface)', color: 'var(--text)',
                            border: '1px solid var(--border)', borderRadius: '7px', fontSize: '0.78rem',
                            fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit',
                          }}
                        >
                          Download
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {total > LIMIT && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '0.75rem', padding: '0.75rem 1rem', borderTop: '1px solid var(--border)' }}>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)' }}>
              Page {page} of {totalPages} · {total} run(s)
            </span>
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              style={{ padding: '5px 12px', border: '1px solid var(--border)', borderRadius: '7px', backgroundColor: 'var(--surface)', color: 'var(--text)', fontSize: '0.78rem', fontWeight: 600, cursor: page <= 1 ? 'not-allowed' : 'pointer', fontFamily: 'inherit', opacity: page <= 1 ? 0.5 : 1 }}
            >
              Prev
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              style={{ padding: '5px 12px', border: '1px solid var(--border)', borderRadius: '7px', backgroundColor: 'var(--surface)', color: 'var(--text)', fontSize: '0.78rem', fontWeight: 600, cursor: page >= totalPages ? 'not-allowed' : 'pointer', fontFamily: 'inherit', opacity: page >= totalPages ? 0.5 : 1 }}
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
