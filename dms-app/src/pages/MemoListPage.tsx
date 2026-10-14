import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'react-hot-toast'
import { memoApi } from '@/api/memo.api'
import type { Memo } from '@/types/memo.types'
import Button from '@/components/ui/Button'

const STATUS_COLORS: Record<string, { bg: string; color: string }> = {
  draft: { bg: '#f1f5f9', color: '#475569' },
  submitted: { bg: '#dbeafe', color: '#1e40af' },
  pending_approval: { bg: '#fef3c7', color: '#92400e' },
  approved: { bg: '#d1fae5', color: '#065f46' },
  rejected: { bg: '#fee2e2', color: '#991b1b' },
  returned: { bg: '#ffedd5', color: '#9a3412' },
  published: { bg: '#ede9fe', color: '#5b21b6' },
  archived: { bg: '#f3f4f6', color: '#374151' },
}

export default function MemoListPage() {
  const navigate = useNavigate()
  const [memos, setMemos] = useState<Memo[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const LIMIT = 20

  useEffect(() => {
    async function load() {
      setLoading(true)
      try {
        const res = await memoApi.list({ skip: (page - 1) * LIMIT, limit: LIMIT })
        setMemos(res.items)
        setTotal(res.total)
      } catch {
        toast.error('Failed to load memos')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [page])

  const statusColor = (status: string | null) => STATUS_COLORS[status || 'draft'] || STATUS_COLORS.draft

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h1 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 600 }}>Memos</h1>
        <Button onClick={() => navigate('/memos/new')}>New Memo</Button>
      </div>

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '3rem' }}>Loading...</div>
      ) : memos.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '3rem', color: '#64748b' }}>
          <p>No memos yet.</p>
          <Button onClick={() => navigate('/memos/new')} style={{ marginTop: '1rem' }}>Create your first memo</Button>
        </div>
      ) : (
        <>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
                  <th style={{ padding: '0.75rem 1rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 600, color: '#64748b', textTransform: 'uppercase' }}>Subject</th>
                  <th style={{ padding: '0.75rem 1rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 600, color: '#64748b', textTransform: 'uppercase' }}>Status</th>
                  <th style={{ padding: '0.75rem 1rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 600, color: '#64748b', textTransform: 'uppercase' }}>Date</th>
                  <th style={{ padding: '0.75rem 1rem', textAlign: 'right', fontSize: '0.75rem', fontWeight: 600, color: '#64748b', textTransform: 'uppercase' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {memos.map((m) => (
                  <tr key={m.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: '1rem' }}>
                      <Link to={`/memos/${m.id}`} style={{ fontWeight: 500, color: '#1e293b', textDecoration: 'none' }}>
                        {m.subject}
                      </Link>
                    </td>
                    <td style={{ padding: '1rem' }}>
                      <span
                        style={{
                          display: 'inline-block',
                          padding: '2px 8px',
                          borderRadius: 9999,
                          fontSize: '0.7rem',
                          fontWeight: 600,
                          ...statusColor(m.workflow_status),
                        }}
                      >
                        {(m.workflow_status || 'draft').replace('_', ' ').toUpperCase()}
                      </span>
                    </td>
                    <td style={{ padding: '1rem', fontSize: '0.85rem', color: '#64748b' }}>
                      {new Date(m.memo_date).toLocaleDateString()}
                    </td>
                    <td style={{ padding: '1rem', textAlign: 'right' }}>
                      <Link
                        to={`/memos/${m.id}`}
                        style={{ fontSize: '0.8rem', color: '#4f46e5', textDecoration: 'none', marginRight: '0.75rem' }}
                      >
                        View
                      </Link>
                      {m.workflow_status === null || m.workflow_status === 'draft' || m.workflow_status === 'returned' ? (
                        <Link
                          to={`/memos/${m.id}/edit`}
                          style={{ fontSize: '0.8rem', color: '#4f46e5', textDecoration: 'none' }}
                        >
                          Edit
                        </Link>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {total > LIMIT && (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '1rem', marginTop: '1.5rem' }}>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                Previous
              </Button>
              <span style={{ fontSize: '0.85rem', color: '#64748b' }}>
                Page {page} of {Math.ceil(total / LIMIT)}
              </span>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setPage((p) => Math.min(Math.ceil(total / LIMIT), p + 1))}
                disabled={page >= Math.ceil(total / LIMIT)}
              >
                Next
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  )
}