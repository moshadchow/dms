import type { AuditLog } from '@/types/audit.types'

interface Props {
  log: AuditLog | null
  isOpen: boolean
  onClose: () => void
}

export default function AuditDetailDrawer({ log, isOpen, onClose }: Props) {
  if (!isOpen || !log) return null

  const parseJson = (val: string | null): Record<string, unknown> | null => {
    if (!val) return null
    try { return JSON.parse(val) } catch { return null }
  }

  const oldVal = parseJson(log.old_value)
  const newVal = parseJson(log.new_value)

  return (
    <>
      {/* Backdrop */}
      <div onClick={onClose} style={{
        position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.3)',
        zIndex: 999, display: 'flex', justifyContent: 'flex-end',
      }}>
        {/* Drawer */}
        <div onClick={(e) => e.stopPropagation()} style={{
          width: '480px', maxWidth: '100vw', height: '100vh',
          backgroundColor: 'var(--surface)', boxShadow: '-4px 0 24px rgba(0,0,0,0.12)',
          overflowY: 'auto', padding: '1.5rem',
        }}>
          {/* Header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.5rem' }}>
            <div>
              <h2 style={{ fontSize: '1rem', fontWeight: 700, margin: 0, color: 'var(--text)' }}>
                Audit Log Detail
              </h2>
              <p style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', margin: '4px 0 0' }}>
                ID: {log.id}
              </p>
            </div>
            <button onClick={onClose} style={{
              background: 'none', border: 'none', cursor: 'pointer', padding: '4px',
              color: 'var(--text-secondary)',
            }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>

          {/* Status badge */}
          <div style={{ marginBottom: '1.5rem' }}>
            <span style={{
              display: 'inline-block', padding: '4px 12px', borderRadius: '999px',
              fontSize: '0.75rem', fontWeight: 600, color: '#fff',
              backgroundColor: log.is_success ? '#10b981' : '#ef4444',
            }}>
              {log.is_success ? 'Success' : 'Failed'}
            </span>
          </div>

          {/* Info sections */}
          <Section title="General">
            <Field label="Timestamp" value={new Date(log.timestamp).toLocaleString()} />
            <Field label="Action" value={formatAction(log.action)} />
            <Field label="Module" value={log.module} />
            <Field label="Description" value={log.description} />
            <Field label="Entity" value={log.entity_name ? `${log.entity_name}${log.entity_id ? `#${log.entity_id}` : ''}` : null} />
          </Section>

          <Section title="User">
            <Field label="User ID" value={log.user_id} />
            <Field label="Username" value={log.username} />
            <Field label="Full Name" value={log.full_name} />
            <Field label="Role" value={log.role} />
            <Field label="User Level" value={log.user_level} />
            <Field label="Auth Provider" value={log.auth_provider} />
          </Section>

          <Section title="Request">
            <Field label="HTTP Method" value={log.http_method} />
            <Field label="Request URL" value={log.request_url} />
            <Field label="HTTP Status" value={log.http_status} />
            <Field label="IP Address" value={log.ip_address} />
          </Section>

          <Section title="Client">
            <Field label="Browser" value={log.browser} />
            <Field label="Operating System" value={log.operating_system} />
            <Field label="Device" value={log.device} />
          </Section>

          {(oldVal || newVal) && (
            <Section title="Change Tracking">
              {oldVal && (
                <div style={{ marginBottom: '0.75rem' }}>
                  <p style={labelStyle}>Previous Value</p>
                  <pre style={jsonStyle}>{JSON.stringify(oldVal, null, 2)}</pre>
                </div>
              )}
              {newVal && (
                <div>
                  <p style={labelStyle}>New Value</p>
                  <pre style={jsonStyle}>{JSON.stringify(newVal, null, 2)}</pre>
                </div>
              )}
            </Section>
          )}

          {log.failure_reason && (
            <Section title="Failure">
              <Field label="Reason" value={log.failure_reason} />
            </Section>
          )}

          <Section title="Tracking">
            <Field label="Correlation ID" value={log.correlation_id} />
            <Field label="Session ID" value={log.session_id} />
            <Field label="Created At" value={new Date(log.created_at).toLocaleString()} />
          </Section>
        </div>
      </div>
    </>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: '1.25rem' }}>
      <h3 style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-tertiary)', margin: '0 0 0.625rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {title}
      </h3>
      <div style={{ backgroundColor: 'var(--bg, #f8fafc)', borderRadius: '0.75rem', border: '1px solid var(--border)', padding: '0.875rem' }}>
        {children}
      </div>
    </div>
  )
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  if (value === null || value === undefined || value === '') return null
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid var(--border)' }}>
      <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', fontWeight: 500 }}>{label}</span>
      <span style={{ fontSize: '0.78rem', color: 'var(--text)', fontWeight: 600, textAlign: 'right', maxWidth: '60%', wordBreak: 'break-word' }}>{String(value)}</span>
    </div>
  )
}

function formatAction(action: string): string {
  return action.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
}

const labelStyle: React.CSSProperties = {
  fontSize: '0.7rem', fontWeight: 600, color: 'var(--text-tertiary)',
  marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.05em',
}

const jsonStyle: React.CSSProperties = {
  backgroundColor: 'var(--surface)', borderRadius: '0.5rem', border: '1px solid var(--border)',
  padding: '0.625rem', fontSize: '0.72rem', fontFamily: 'monospace', overflowX: 'auto',
  margin: 0, lineHeight: 1.5, color: 'var(--text)',
}
