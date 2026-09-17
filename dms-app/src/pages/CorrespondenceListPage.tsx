import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { correspondenceApi, type CorrespondenceListParams } from '@/api/correspondence.api'
import type { Correspondence, CorrespondenceDirection, CorrespondencePriority, CorrespondenceStatus } from '@/types/correspondence.types'
import CorrespondenceFilters from '@/components/correspondence/CorrespondenceFilters'
import CorrespondenceTable from '@/components/correspondence/CorrespondenceTable'
import Button from '@/components/ui/Button'
import { getErrorMessage } from '@/api/client'

type TabKey = 'all' | 'inbound' | 'outbound' | 'internal' | 'pending' | 'overdue'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'inbound', label: 'Incoming' },
  { key: 'outbound', label: 'Outgoing' },
  { key: 'internal', label: 'Internal' },
  { key: 'pending', label: 'Pending Actions' },
  { key: 'overdue', label: 'Overdue' },
]

export default function CorrespondenceListPage() {
  const navigate = useNavigate()
  const [items, setItems] = useState<Correspondence[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<TabKey>('all')
  const [direction, setDirection] = useState<CorrespondenceDirection | ''>('')
  const [priority, setPriority] = useState<CorrespondencePriority | ''>('')
  const [status, setStatus] = useState<CorrespondenceStatus | ''>('')
  const [search, setSearch] = useState('')
  const [responseRequired, setResponseRequired] = useState<boolean | null>(null)
  const [page, setPage] = useState(0)
  const limit = 20

  const fetchCorrespondences = useCallback(async () => {
    setLoading(true)
    try {
      const params: CorrespondenceListParams = { skip: page * limit, limit }
      // Tab overrides
      if (tab === 'inbound') params.direction = 'inbound'
      else if (tab === 'outbound') params.direction = 'outbound'
      else if (tab === 'internal') params.direction = 'internal'
      else if (tab === 'pending') params.status = 'pending_approval'
      else if (tab === 'overdue') params.overdue = true

      // Explicit filters (take precedence over tab for direction)
      if (direction) params.direction = direction
      if (priority) params.priority = priority
      if (status && tab !== 'pending') params.status = status
      if (responseRequired !== null) params.response_required = responseRequired
      if (search) params.search = search

      const res = await correspondenceApi.list(params)
      setItems(res.items)
      setTotal(res.total)
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [tab, direction, priority, status, search, responseRequired, page])

  useEffect(() => { fetchCorrespondences() }, [fetchCorrespondences])

  const handleTabChange = (newTab: TabKey) => {
    setTab(newTab)
    setPage(0)
    // Reset direction filter when switching tabs
    setDirection('')
    setStatus('')
  }

  const handleReset = () => {
    setDirection('')
    setPriority('')
    setStatus('')
    setSearch('')
    setResponseRequired(null)
    setPage(0)
  }

  return (
    <div style={{ padding: '1.5rem', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--text)', margin: 0 }}>Correspondence</h1>
        <div style={{ display: 'flex', gap: '8px' }}>
          <Button onClick={() => navigate('/correspondence/new?direction=inbound')} variant="outline" size="sm">+ Incoming</Button>
          <Button onClick={() => navigate('/correspondence/new?direction=outbound')} variant="outline" size="sm">+ Outgoing</Button>
          <Button onClick={() => navigate('/correspondence/new?direction=internal')} size="sm">+ Internal</Button>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '4px', borderBottom: '2px solid var(--border)', marginBottom: '1rem' }}>
        {TABS.map(t => (
          <button
            key={t.key}
            onClick={() => handleTabChange(t.key)}
            style={{
              padding: '8px 14px', borderRadius: '6px 6px 0 0', border: 'none',
              backgroundColor: tab === t.key ? 'var(--primary-soft)' : 'transparent',
              color: tab === t.key ? 'var(--primary)' : 'var(--text-secondary)',
              fontWeight: tab === t.key ? 600 : 400, fontSize: '0.82rem',
              cursor: 'pointer', transition: 'all 150ms',
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Filters */}
      <div style={{ marginBottom: '1rem' }}>
        <CorrespondenceFilters
          direction={direction}
          onDirectionChange={(v) => { setDirection(v); setPage(0) }}
          priority={priority}
          onPriorityChange={(v) => { setPriority(v); setPage(0) }}
          status={status}
          onStatusChange={(v) => { setStatus(v); setPage(0) }}
          search={search}
          onSearchChange={(v) => { setSearch(v); setPage(0) }}
          responseRequired={responseRequired}
          onResponseRequiredChange={(v) => { setResponseRequired(v); setPage(0) }}
          onReset={handleReset}
        />
      </div>

      {/* Table */}
      <div style={{ backgroundColor: 'var(--surface)', borderRadius: '8px', border: '1px solid var(--border)', overflow: 'hidden' }}>
        <CorrespondenceTable items={items} loading={loading} />
      </div>

      {/* Pagination */}
      {total > limit && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1rem', fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
          <span>Showing {page * limit + 1}–{Math.min((page + 1) * limit, total)} of {total}</span>
          <div style={{ display: 'flex', gap: '8px' }}>
            <Button variant="secondary" size="sm" disabled={page === 0} onClick={() => setPage(p => p - 1)}>Previous</Button>
            <Button variant="secondary" size="sm" disabled={(page + 1) * limit >= total} onClick={() => setPage(p => p + 1)}>Next</Button>
          </div>
        </div>
      )}
    </div>
  )
}
