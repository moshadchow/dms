import type { AuditLog } from '@/types/audit.types'

interface Props {
  logs: AuditLog[]
  loading: boolean
  onViewDetail: (log: AuditLog) => void
}

const MODULE_COLORS: Record<string, string> = {
  auth: '#8b5cf6',
  users: '#3b82f6',
  documents: '#10b981',
  directories: '#f59e0b',
  categories: '#ec4899',
  user_levels: '#06b6d4',
  security: '#ef4444',
}

export default function AuditTable({ logs, loading, onViewDetail }: Props) {
  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '3rem' }}>
        <div style={{
          width: '28px', height: '28px',
          border: '3px solid #e2e8f0', borderTopColor: '#4f46e5',
          borderRadius: '50%', animation: 'spin 0.7s linear infinite',
        }} />
        <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
      </div>
    )
  }

  if (logs.length === 0) {
    return (
      <div style={{ padding: '3rem', textAlign: 'center' }}>
        <p style={{ color: 'var(--text-tertiary)', fontSize: '0.875rem' }}>No audit logs found</p>
      </div>
    )
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border)' }}>
            <th style={thStyle}>Timestamp</th>
            <th style={thStyle}>User</th>
            <th style={thStyle}>Action</th>
            <th style={thStyle}>Module</th>
            <th style={thStyle}>Entity</th>
            <th style={thStyle}>Status</th>
            <th style={thStyle}>IP</th>
            <th style={{ ...thStyle, textAlign: 'center' }}>Details</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((log) => (
            <tr key={log.id} style={{ borderBottom: '1px solid var(--border)', cursor: 'pointer' }}
              onClick={() => onViewDetail(log)}>
              <td style={tdStyle}>
                {new Date(log.timestamp).toLocaleString()}
              </td>
              <td style={tdStyle}>
                <div>
                  <span style={{ fontWeight: 600 }}>{log.full_name || log.username || 'System'}</span>
                  {log.role && (
                    <span style={{ display: 'block', fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>
                      {log.role}
                    </span>
                  )}
                </div>
              </td>
              <td style={tdStyle}>
                <span style={{ fontWeight: 500 }}>{formatAction(log.action)}</span>
              </td>
              <td style={tdStyle}>
                <span style={{
                  display: 'inline-block', padding: '2px 8px', borderRadius: '999px',
                  fontSize: '0.7rem', fontWeight: 600, color: '#fff',
                  backgroundColor: MODULE_COLORS[log.module] || '#6b7280',
                }}>
                  {log.module}
                </span>
              </td>
              <td style={tdStyle}>
                {log.entity_name && (
                  <span>
                    {log.entity_name}
                    {log.entity_id && <span style={{ color: 'var(--text-tertiary)' }}>#{log.entity_id}</span>}
                  </span>
                )}
              </td>
              <td style={tdStyle}>
                <span style={{
                  display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%',
                  backgroundColor: log.is_success ? '#10b981' : '#ef4444',
                  marginRight: '6px',
                }} />
                {log.is_success ? 'Success' : 'Failed'}
              </td>
              <td style={tdStyle}>
                <span style={{ color: 'var(--text-tertiary)', fontFamily: 'monospace', fontSize: '0.75rem' }}>
                  {log.ip_address || '-'}
                </span>
              </td>
              <td style={{ ...tdStyle, textAlign: 'center' }}>
                <button onClick={(e) => { e.stopPropagation(); onViewDetail(log) }}
                  style={{
                    padding: '4px 10px', borderRadius: '6px', border: '1px solid var(--border)',
                    backgroundColor: 'var(--surface)', cursor: 'pointer', fontSize: '0.75rem',
                    color: 'var(--text-secondary)', fontFamily: 'inherit',
                  }}>
                  View
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function formatAction(action: string): string {
  return action.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
}

const thStyle: React.CSSProperties = {
  padding: '0.75rem 1rem', textAlign: 'left', fontWeight: 600,
  color: 'var(--text-secondary)', fontSize: '0.75rem', textTransform: 'uppercase',
  letterSpacing: '0.05em', whiteSpace: 'nowrap',
}

const tdStyle: React.CSSProperties = {
  padding: '0.75rem 1rem', color: 'var(--text)', verticalAlign: 'middle',
}
