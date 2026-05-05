interface Props {
  icon?:        React.ReactNode
  title:        string
  description?: string
  action?:      React.ReactNode
  compact?:     boolean
}

const DEFAULT_ICON = (
  <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#e2e8f0" strokeWidth="1.5">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
    <polyline points="14 2 14 8 20 8"/>
  </svg>
)

export default function EmptyState({ icon = DEFAULT_ICON, title, description, action, compact }: Props) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', textAlign: 'center',
      padding: compact ? '1.5rem 1rem' : '3rem 2rem',
    }}>
      <div style={{ marginBottom: '0.875rem', opacity: 0.7 }}>{icon}</div>
      <p style={{ fontWeight: 600, color: '#94a3b8', margin: 0, fontSize: compact ? '0.85rem' : '0.95rem' }}>
        {title}
      </p>
      {description && (
        <p style={{ color: '#cbd5e1', fontSize: '0.8rem', margin: '6px 0 0', lineHeight: 1.6, maxWidth: '280px' }}>
          {description}
        </p>
      )}
      {action && <div style={{ marginTop: '1rem' }}>{action}</div>}
    </div>
  )
}
