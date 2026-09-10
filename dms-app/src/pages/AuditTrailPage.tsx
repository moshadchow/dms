import { useState, useEffect, useCallback } from 'react'
import { toast } from 'react-hot-toast'
import { auditApi } from '@/api/audit.api'
import AuditTable from '@/components/admin/AuditTable'
import AuditFilters from '@/components/admin/AuditFilters'
import AuditDetailDrawer from '@/components/admin/AuditDetailDrawer'
import CompanyContextDropdown from '@/components/admin/CompanyContextDropdown'
import { useAuthStore } from '@/store/authStore'
import type { AuditLog, AuditLogFilters } from '@/types/audit.types'

const LIMIT = 50

export default function AuditTrailPage() {
  const isSuperAdmin = useAuthStore((s) => s.isSuperAdmin())
  const userCompanyId = useAuthStore((s) => s.user?.company_id ?? null)

  const [selectedCompanyId, setSelectedCompanyId] = useState<number | null>(
    isSuperAdmin ? null : userCompanyId,
  )
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState<AuditLogFilters>({})
  const [selectedLog, setSelectedLog] = useState<AuditLog | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)

  const effectiveCompanyId = isSuperAdmin ? selectedCompanyId : userCompanyId

  const loadLogs = useCallback(async () => {
    if (isSuperAdmin && !selectedCompanyId) {
      setLogs([])
      setTotal(0)
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const data = await auditApi.list({
        ...filters,
        company_id: effectiveCompanyId ?? undefined,
        skip: (page - 1) * LIMIT,
        limit: LIMIT,
      })
      setLogs(data.items)
      setTotal(data.total)
    } catch {
      toast.error('Failed to load audit logs')
    } finally {
      setLoading(false)
    }
  }, [page, filters, effectiveCompanyId, isSuperAdmin, selectedCompanyId])

  useEffect(() => { loadLogs() }, [loadLogs])
  useEffect(() => { setPage(1) }, [filters, effectiveCompanyId])

  const handleCompanyChange = (companyId: number | null) => {
    setSelectedCompanyId(companyId)
    setLogs([])
    setTotal(0)
  }

  const totalPages = Math.ceil(total / LIMIT) || 1

  const handleExport = async (format: 'csv' | 'excel') => {
    try {
      const blob = await auditApi.export({
        ...filters,
        company_id: effectiveCompanyId ?? undefined,
      }, format)
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `audit-logs.${format === 'csv' ? 'csv' : 'xlsx'}`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      toast.success(`Exported audit logs as ${format.toUpperCase()}`)
    } catch {
      toast.error('Failed to export audit logs')
    }
  }

  const handleViewDetail = (log: AuditLog) => {
    setSelectedLog(log)
    setDrawerOpen(true)
  }

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
            Audit Trail
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.82rem', margin: '3px 0 0' }}>
            System activity logs and security events
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          {isSuperAdmin && (
            <CompanyContextDropdown value={selectedCompanyId} onChange={handleCompanyChange} />
          )}
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              onClick={() => handleExport('csv')}
              style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                padding: '7px 14px', backgroundColor: 'var(--surface)', color: 'var(--text)',
                border: '1px solid var(--border)', borderRadius: '8px', fontSize: '0.85rem',
                fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit',
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" />
              </svg>
              CSV
            </button>
            <button
              onClick={() => handleExport('excel')}
              style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                padding: '7px 14px', backgroundColor: 'var(--text)', color: 'var(--surface)',
                border: 'none', borderRadius: '8px', fontSize: '0.85rem',
                fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit',
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" />
              </svg>
              Excel
            </button>
          </div>
        </div>
      </div>

      {/* Empty state for SUPERADMIN without company selected */}
      {isSuperAdmin && !selectedCompanyId ? (
        <div style={{
          backgroundColor: 'var(--surface)', borderRadius: '1rem',
          border: '1px solid var(--border)', padding: '3rem 1.5rem',
          textAlign: 'center',
        }}>
          <p style={{ fontSize: '1rem', color: 'var(--text-secondary)', margin: 0 }}>
            Please select a company to view audit logs.
          </p>
        </div>
      ) : (
        <>
          {/* Stats */}
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
            gap: '0.75rem', marginBottom: '1.25rem',
          }}>
            {[
              { label: 'Total events', value: total, color: 'var(--primary)', icon: '📋' },
              { label: 'Successful', value: logs.filter(l => l.is_success).length, color: 'var(--success)', icon: '✅' },
              { label: 'Failed', value: logs.filter(l => !l.is_success).length, color: 'var(--danger, #ef4444)', icon: '❌' },
              { label: 'Unique users', value: new Set(logs.filter(l => l.user_id).map(l => l.user_id)).size, color: 'var(--warning)', icon: '👥' },
            ].map((s) => (
              <div key={s.label} style={{
                backgroundColor: 'var(--surface)', borderRadius: '0.875rem',
                border: '1px solid var(--border)', padding: '1rem 1.125rem',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <p style={{ fontSize: '1.4rem', fontWeight: 700, color: s.color, margin: 0 }}>{s.value}</p>
                  <span style={{ fontSize: '1.25rem' }}>{s.icon}</span>
                </div>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', margin: '2px 0 0', fontWeight: 500 }}>{s.label}</p>
              </div>
            ))}
          </div>

          {/* Main card */}
          <div style={{
            backgroundColor: 'var(--surface)', borderRadius: '1rem',
            border: '1px solid var(--border)', overflow: 'hidden',
          }}>
            <AuditFilters filters={filters} onChange={setFilters} />
            <AuditTable logs={logs} loading={loading} onViewDetail={handleViewDetail} />

            {totalPages > 1 && (
              <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                gap: '0.5rem', padding: '1rem', borderTop: '1px solid var(--border)',
              }}>
                <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} style={pageBtn}>←</button>
                <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>Page {page} of {totalPages}</span>
                <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages} style={pageBtn}>→</button>
              </div>
            )}
          </div>
        </>
      )}

      <AuditDetailDrawer log={selectedLog} isOpen={drawerOpen} onClose={() => { setDrawerOpen(false); setSelectedLog(null) }} />
    </div>
  )
}

const pageBtn: React.CSSProperties = {
  padding: '5px 12px', borderRadius: '7px', border: '1px solid var(--border-soft)',
  backgroundColor: 'var(--surface)', color: 'var(--text-secondary)', fontSize: '0.82rem',
  cursor: 'pointer', fontFamily: 'inherit',
}
