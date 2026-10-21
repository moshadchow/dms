import { useState, useEffect, useCallback } from 'react'
import { toast } from 'react-hot-toast'
import { backupsApi } from '@/api/backups.api'
import CompanyContextDropdown from '@/components/admin/CompanyContextDropdown'
import { useAuthStore } from '@/store/authStore'
import { getErrorMessage } from '@/api/client'
import type { BackupRun, BackupSettings, BackupStatus, BackupTrigger } from '@/types/backup.types'

const LIMIT = 50

const STATUS_META: Record<BackupStatus, { label: string; color: string; bg: string }> = {
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

function StatusBadge({ status }: { status: BackupStatus }) {
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

function TriggerBadge({ trigger }: { trigger: BackupTrigger }) {
  return (
    <span style={{
      padding: '2px 8px', borderRadius: '6px', fontSize: '0.72rem', fontWeight: 600,
      color: 'var(--text-secondary)', backgroundColor: 'var(--surface-2)',
    }}>
      {trigger === 'manual' ? 'Manual' : 'Scheduled'}
    </span>
  )
}

export default function BackupsPage() {
  const isSuperAdmin = useAuthStore((s) => s.isSuperAdmin())
  const userCompanyId = useAuthStore((s) => s.user?.company_id ?? null)

  const [selectedCompanyId, setSelectedCompanyId] = useState<number | null>(
    isSuperAdmin ? null : userCompanyId,
  )
  const [runs, setRuns] = useState<BackupRun[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [runningNow, setRunningNow] = useState(false)

  const [settings, setSettings] = useState<BackupSettings | null>(null)
  const [savingSettings, setSavingSettings] = useState(false)

  const effectiveCompanyId = isSuperAdmin ? selectedCompanyId : userCompanyId

  const loadRuns = useCallback(() => {
    Promise.resolve()
      .then(() => {
        if (isSuperAdmin && !selectedCompanyId) {
          setRuns([])
          setTotal(0)
          setLoading(false)
          return Promise.resolve()
        }
        setLoading(true)
        return backupsApi.list({
          company_id: effectiveCompanyId ?? undefined,
          skip: (page - 1) * LIMIT,
          limit: LIMIT,
        })
      })
      .then((data) => {
        if (data) {
          setRuns(data.items)
          setTotal(data.total)
        }
      })
      .catch((err) => toast.error(getErrorMessage(err)))
      .finally(() => setLoading(false))
  }, [page, effectiveCompanyId, isSuperAdmin, selectedCompanyId])

  useEffect(() => { loadRuns() }, [loadRuns])

  // Reset page when the company scope changes (adjusted during render)
  const [prevCompanyId, setPrevCompanyId] = useState(effectiveCompanyId)
  if (prevCompanyId !== effectiveCompanyId) {
    setPrevCompanyId(effectiveCompanyId)
    setPage(1)
  }

  useEffect(() => {
    backupsApi.getSettings()
      .then(setSettings)
      .catch((err) => toast.error(getErrorMessage(err)))
  }, [])

  const handleRunNow = () => {
    setRunningNow(true)
    backupsApi.runNow()
      .then((run) => {
        if (run.status === 'success') {
          toast.success(`Backup completed — ${run.file_count} file(s) archived`)
        } else {
          toast.error(run.error_message || 'Backup failed')
        }
        loadRuns()
      })
      .catch((err) => toast.error(getErrorMessage(err)))
      .finally(() => setRunningNow(false))
  }

  const handleSaveSettings = () => {
    if (!settings) return
    setSavingSettings(true)
    backupsApi.updateSettings({
      enabled: settings.enabled,
      interval_hours: settings.interval_hours,
      retention_count: settings.retention_count,
    })
      .then((updated) => {
        setSettings(updated)
        toast.success('Backup settings saved')
        loadRuns()
      })
      .catch((err) => toast.error(getErrorMessage(err)))
      .finally(() => setSavingSettings(false))
  }

  const handleDownload = (run: BackupRun) => {
    if (!run.archive_path) return
    const fileName = run.archive_path.split('/').pop() || 'backup.zip'
    backupsApi.download(run.id, fileName)
      .then(() => toast.success('Backup archive downloaded'))
      .catch((err) => toast.error(getErrorMessage(err)))
  }

  const totalPages = Math.ceil(total / LIMIT) || 1

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
            Folder Backups
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.82rem', margin: '3px 0 0' }}>
            Automated company-wise folder backup service
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          {isSuperAdmin && (
            <CompanyContextDropdown value={selectedCompanyId} onChange={setSelectedCompanyId} />
          )}
          <button
            onClick={handleRunNow}
            disabled={runningNow || (isSuperAdmin && !selectedCompanyId)}
            style={{
              display: 'flex', alignItems: 'center', gap: '6px',
              padding: '7px 14px', backgroundColor: 'var(--text)', color: 'var(--surface)',
              border: 'none', borderRadius: '8px', fontSize: '0.85rem',
              fontWeight: 600, cursor: runningNow ? 'not-allowed' : 'pointer',
              fontFamily: 'inherit', opacity: runningNow ? 0.7 : 1,
            }}
          >
            {runningNow ? 'Backing up…' : 'Run backup now'}
          </button>
        </div>
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
              Automatic backups enabled
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
              Archives kept per company (1–100)
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
            Loading backup runs…
          </div>
        ) : runs.length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-tertiary)', fontSize: '0.85rem' }}>
            No backup runs yet — click “Run backup now” to create the first archive.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-tertiary)', textAlign: 'left' }}>
                  <th style={{ padding: '10px 14px', fontWeight: 600 }}>Status</th>
                  <th style={{ padding: '10px 14px', fontWeight: 600 }}>Trigger</th>
                  {isSuperAdmin && <th style={{ padding: '10px 14px', fontWeight: 600 }}>Company</th>}
                  <th style={{ padding: '10px 14px', fontWeight: 600 }}>Started</th>
                  <th style={{ padding: '10px 14px', fontWeight: 600 }}>Finished</th>
                  <th style={{ padding: '10px 14px', fontWeight: 600 }}>Files</th>
                  <th style={{ padding: '10px 14px', fontWeight: 600 }}>Archive</th>
                  <th style={{ padding: '10px 14px', fontWeight: 600 }} />
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.id} style={{ borderBottom: '1px solid var(--border)', color: 'var(--text)' }}>
                    <td style={{ padding: '10px 14px' }}>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                        <StatusBadge status={run.status} />
                        {run.error_message && (
                          <span style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', maxWidth: '220px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={run.error_message}>
                            {run.error_message}
                          </span>
                        )}
                      </div>
                    </td>
                    <td style={{ padding: '10px 14px' }}><TriggerBadge trigger={run.trigger} /></td>
                    {isSuperAdmin && <td style={{ padding: '10px 14px' }}>{run.company_short_name ?? `#${run.company_id}`}</td>}
                    <td style={{ padding: '10px 14px' }}>{formatDateTime(run.started_at)}</td>
                    <td style={{ padding: '10px 14px' }}>{formatDateTime(run.finished_at)}</td>
                    <td style={{ padding: '10px 14px' }}>{run.file_count} ({formatBytes(run.total_bytes)})</td>
                    <td style={{ padding: '10px 14px' }}>
                      {run.archive_path ? formatBytes(run.archive_size_bytes) : 'Pruned'}
                    </td>
                    <td style={{ padding: '10px 14px' }}>
                      {run.archive_path && (
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
