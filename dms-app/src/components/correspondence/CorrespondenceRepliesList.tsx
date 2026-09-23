import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { correspondenceApi } from '@/api/correspondence.api'
import type { CorrespondenceDetail } from '@/types/correspondence.types'
import { formatDateTime } from '@/utils/formatters'

interface Props {
  parentId: number
  refreshKey?: number
}

const STATUS_BADGES: Record<string, { bg: string; color: string }> = {
  draft: { bg: '#f1f5f9', color: '#64748b' }, received: { bg: '#dbeafe', color: '#1e40af' },
  submitted: { bg: '#e0e7ff', color: '#3730a3' }, pending_approval: { bg: '#fef3c7', color: '#92400e' },
  approved: { bg: '#d1fae5', color: '#065f46' }, ready_for_dispatch: { bg: '#d1fae5', color: '#065f46' },
  dispatched: { bg: '#e0e7ff', color: '#3730a3' }, delivered: { bg: '#d1fae5', color: '#065f46' },
  acknowledged: { bg: '#d1fae5', color: '#065f46' }, completed: { bg: '#d1fae5', color: '#065f46' },
  cancelled: { bg: '#f1f5f9', color: '#64748b' }, archived: { bg: '#f1f5f9', color: '#64748b' },
  rejected: { bg: '#fee2e2', color: '#dc2626' }, returned: { bg: '#ffedd5', color: '#c2410c' },
}

export default function CorrespondenceRepliesList({ parentId, refreshKey }: Props) {
  const navigate = useNavigate()
  const [replies, setReplies] = useState<CorrespondenceDetail[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    correspondenceApi.getReplies(parentId)
      .then(data => { if (active) setReplies(data) })
      .catch(() => { if (active) setReplies([]) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [parentId, refreshKey])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      {loading ? (
        <div style={{ fontSize: '0.82rem', color: 'var(--text-tertiary)' }}>Loading replies...</div>
      ) : replies.length === 0 ? (
        <div style={{ fontSize: '0.82rem', color: 'var(--text-tertiary)' }}>No replies yet</div>
      ) : (
        replies.map((reply) => {
          const badge = STATUS_BADGES[reply.status] ?? STATUS_BADGES.draft
          return (
            <button
              key={reply.id}
              onClick={() => navigate(`/correspondence/${reply.id}`)}
              style={{
                display: 'flex', flexDirection: 'column', gap: '4px', textAlign: 'left',
                padding: '8px 10px', borderRadius: '6px', border: '1px solid var(--border)',
                backgroundColor: 'var(--surface)', cursor: 'pointer', fontFamily: 'inherit',
                width: '100%', boxSizing: 'border-box',
              }}
            >
              <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
                <strong style={{ color: 'var(--primary)', fontSize: '0.8rem' }}>{reply.reference_number}</strong>
                <span style={{ padding: '1px 6px', borderRadius: 999, fontSize: '0.68rem', fontWeight: 600, backgroundColor: badge.bg, color: badge.color }}>
                  {reply.status.replace(/_/g, ' ')}
                </span>
              </span>
              <span style={{ fontSize: '0.82rem', color: 'var(--text)', fontWeight: 500 }}>{reply.subject}</span>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>
                {reply.created_by_name || 'Unknown'} · {formatDateTime(reply.created_at)}
              </span>
            </button>
          )
        })
      )}
    </div>
  )
}