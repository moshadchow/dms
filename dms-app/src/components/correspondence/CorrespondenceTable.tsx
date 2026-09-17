import { useNavigate } from 'react-router-dom'
import type { Correspondence, CorrespondenceDirection, CorrespondencePriority, CorrespondenceStatus } from '@/types/correspondence.types'
import { formatDateTime } from '@/utils/formatters'

interface Props {
  items: Correspondence[]
  loading: boolean
}

const PRIORITY_BADGES: Record<CorrespondencePriority, { bg: string; color: string }> = {
  low:    { bg: '#f1f5f9', color: '#64748b' },
  normal: { bg: '#dbeafe', color: '#1e40af' },
  high:   { bg: '#ffedd5', color: '#c2410c' },
  urgent: { bg: '#fee2e2', color: '#dc2626' },
}

const STATUS_BADGES: Record<string, { bg: string; color: string }> = {
  draft:             { bg: '#f1f5f9', color: '#64748b' },
  received:          { bg: '#dbeafe', color: '#1e40af' },
  registered:        { bg: '#dbeafe', color: '#1e40af' },
  assigned:          { bg: '#e0e7ff', color: '#3730a3' },
  processing:        { bg: '#fef3c7', color: '#92400e' },
  submitted:         { bg: '#e0e7ff', color: '#3730a3' },
  pending_approval:  { bg: '#fef3c7', color: '#92400e' },
  returned:          { bg: '#ffedd5', color: '#c2410c' },
  rejected:          { bg: '#fee2e2', color: '#dc2626' },
  approved:          { bg: '#d1fae5', color: '#065f46' },
  ready_for_dispatch:{ bg: '#d1fae5', color: '#065f46' },
  dispatched:        { bg: '#e0e7ff', color: '#3730a3' },
  delivered:         { bg: '#d1fae5', color: '#065f46' },
  acknowledged:      { bg: '#d1fae5', color: '#065f46' },
  completed:         { bg: '#d1fae5', color: '#065f46' },
  cancelled:         { bg: '#f1f5f9', color: '#64748b' },
  archived:          { bg: '#f1f5f9', color: '#64748b' },
}

const DIRECTION_BADGES: Record<CorrespondenceDirection, { bg: string; color: string; label: string }> = {
  inbound:  { bg: '#dbeafe', color: '#1e40af', label: 'IN' },
  outbound: { bg: '#d1fae5', color: '#065f46', label: 'OUT' },
  internal: { bg: '#fef3c7', color: '#92400e', label: 'INT' },
}

const th: React.CSSProperties = {
  padding: '8px 10px', textAlign: 'left', fontSize: '0.75rem', fontWeight: 600,
  color: 'var(--text-tertiary)', borderBottom: '2px solid var(--border)',
  whiteSpace: 'nowrap',
}

const td: React.CSSProperties = {
  padding: '8px 10px', fontSize: '0.82rem', color: 'var(--text)',
  borderBottom: '1px solid var(--border)',
}

const badge = (bg: string, color: string): React.CSSProperties => ({
  display: 'inline-block', padding: '2px 8px', borderRadius: '999px',
  fontSize: '0.7rem', fontWeight: 600, backgroundColor: bg, color,
  whiteSpace: 'nowrap',
})

const isOverdue = (c: Correspondence): boolean => {
  if (!c.response_required || c.response_received || !c.response_deadline) return false
  if (['completed', 'cancelled', 'archived', 'rejected'].includes(c.status)) return false
  return new Date(c.response_deadline) < new Date()
}

export default function CorrespondenceTable({ items, loading }: Props) {
  const navigate = useNavigate()

  if (loading) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-tertiary)' }}>
        Loading...
      </div>
    )
  }

  if (!items.length) {
    return (
      <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-tertiary)' }}>
        No correspondence found.
      </div>
    )
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th style={th}>Reference</th>
            <th style={th}>Direction</th>
            <th style={th}>Subject</th>
            <th style={th}>Sender / Recipient</th>
            <th style={th}>Priority</th>
            <th style={th}>Status</th>
            <th style={th}>Response</th>
            <th style={th}>Due Date</th>
            <th style={th}>Created</th>
          </tr>
        </thead>
        <tbody>
          {items.map(c => {
            const dDir = DIRECTION_BADGES[c.direction]
            const overdue = isOverdue(c)
            return (
              <tr
                key={c.id}
                onClick={() => navigate(`/correspondence/${c.id}`)}
                style={{ cursor: 'pointer', transition: 'background-color 100ms' }}
                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--surface-2)'}
                onMouseLeave={(e) => e.currentTarget.style.backgroundColor = ''}
              >
                <td style={{ ...td, fontWeight: 600, color: 'var(--primary)' }}>{c.reference_number}</td>
                <td style={td}><span style={badge(dDir.bg, dDir.color)}>{dDir.label}</span></td>
                <td style={{ ...td, maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.subject}</td>
                <td style={td}>
                  {c.direction === 'inbound'
                    ? (c.sender_name || '—')
                    : (c.recipient_name || '—')}
                </td>
                <td style={td}><span style={badge(PRIORITY_BADGES[c.priority].bg, PRIORITY_BADGES[c.priority].color)}>{c.priority}</span></td>
                <td style={td}><span style={badge(STATUS_BADGES[c.status]?.bg ?? '#f1f5f9', STATUS_BADGES[c.status]?.color ?? '#64748b')}>{c.status.replace(/_/g, ' ')}</span></td>
                <td style={td}>
                  {c.response_required
                    ? <span style={{ color: c.response_received ? 'var(--success)' : overdue ? 'var(--danger)' : 'var(--warning)', fontWeight: 600, fontSize: '0.78rem' }}>{c.response_received ? 'Received' : overdue ? 'Overdue' : 'Required'}</span>
                    : <span style={{ color: 'var(--text-tertiary)' }}>—</span>}
                </td>
                <td style={{ ...td, color: overdue ? 'var(--danger)' : 'var(--text-secondary)' }}>
                  {c.response_deadline ? formatDateTime(c.response_deadline) : '—'}
                </td>
                <td style={td}>{formatDateTime(c.created_at)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
