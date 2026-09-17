import type { CorrespondenceMovement } from '@/types/correspondence.types'
import { formatDateTime } from '@/utils/formatters'

interface Props {
  movements: CorrespondenceMovement[]
}

const ACTION_LABELS: Record<string, { color: string; label: string }> = {
  assign:     { color: 'var(--info)', label: 'Assigned' },
  forward:    { color: 'var(--accent)', label: 'Forwarded' },
  dispatch:   { color: 'var(--primary)', label: 'Dispatched' },
  delivered:  { color: 'var(--success)', label: 'Delivered' },
  acknowledged: { color: 'var(--success)', label: 'Acknowledged' },
  return:     { color: 'var(--warning)', label: 'Returned' },
}

export default function CorrespondenceTimeline({ movements }: Props) {
  if (!movements.length) {
    return <div style={{ padding: '1rem', color: 'var(--text-tertiary)', fontSize: '0.82rem' }}>No movement history.</div>
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', padding: '0.5rem 0' }}>
      {movements.map((m, i) => {
        const action = ACTION_LABELS[m.action] ?? { color: 'var(--text-secondary)', label: m.action }
        return (
          <div key={m.id} style={{ display: 'flex', gap: '12px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: '12px', flexShrink: 0 }}>
              <div style={{
                width: '10px', height: '10px', borderRadius: '50%',
                backgroundColor: action.color, flexShrink: 0,
                marginTop: '4px',
              }} />
              {i < movements.length - 1 && (
                <div style={{ width: '2px', flex: 1, backgroundColor: 'var(--border)', marginTop: '4px' }} />
              )}
            </div>
            <div style={{ flex: 1, paddingBottom: '4px' }}>
              <div style={{ fontSize: '0.82rem', fontWeight: 600, color: action.color }}>{action.label}</div>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
                {m.from_user_name && m.to_user_name
                  ? `${m.from_user_name} → ${m.to_user_name}`
                  : m.to_user_name
                    ? `To: ${m.to_user_name}`
                    : m.created_by_name || 'System'}
              </div>
              {m.remarks && (
                <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginTop: '2px', fontStyle: 'italic' }}>
                  {m.remarks}
                </div>
              )}
              <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', marginTop: '4px' }}>
                {formatDateTime(m.created_at)}
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
