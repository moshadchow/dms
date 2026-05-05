interface Props {
  isOpen:    boolean
  title:     string
  message:   string
  confirmLabel?: string
  danger?:   boolean
  loading?:  boolean
  onConfirm: () => void
  onCancel:  () => void
}

export default function ConfirmDialog({ isOpen, title, message, confirmLabel = 'Confirm', danger = false, loading = false, onConfirm, onCancel }: Props) {
  if (!isOpen) return null

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 60, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem' }}>
      <div style={{ position: 'absolute', inset: 0, backgroundColor: 'rgba(15,23,42,0.45)', backdropFilter: 'blur(2px)' }} onClick={onCancel} />
      <div style={{ position: 'relative', width: '100%', maxWidth: '380px', backgroundColor: 'var(--surface)', borderRadius: '1rem', boxShadow: '0 20px 60px rgba(0,0,0,0.15)', padding: '1.5rem', border: '1px solid var(--border)' }}>

        {/* Icon */}
        <div style={{ width: '44px', height: '44px', borderRadius: '12px', backgroundColor: danger ? '#fef2f2' : 'var(--surface-2)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '1rem' }}>
          {danger ? (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#dc2626" strokeWidth="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg>
          ) : (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#475569" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          )}
        </div>

        <h3 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text)', margin: '0 0 0.5rem' }}>{title}</h3>
        <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', margin: '0 0 1.5rem', lineHeight: 1.6 }}>{message}</p>

        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button onClick={onCancel} disabled={loading} style={{ flex: 1, padding: '0.625rem', backgroundColor: 'var(--bg)', color: 'var(--text-secondary)', border: '1px solid var(--border-soft)', borderRadius: '0.5rem', fontSize: '0.875rem', fontWeight: 500, cursor: 'pointer', fontFamily: 'inherit' }}>
            Cancel
          </button>
          <button onClick={onConfirm} disabled={loading} style={{ flex: 1, padding: '0.625rem', backgroundColor: danger ? '#dc2626' : 'var(--text)', color: 'var(--surface)', border: 'none', borderRadius: '0.5rem', fontSize: '0.875rem', fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}>
            {loading ? <><span style={{ width: '14px', height: '14px', border: '2px solid rgba(255,255,255,0.3)', borderTopColor: 'var(--surface)', borderRadius: '50%', animation: 'spin 0.7s linear infinite', display: 'inline-block' }} />{confirmLabel}…</> : confirmLabel}
          </button>
        </div>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    </div>
  )
}
