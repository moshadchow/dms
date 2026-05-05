import { useEffect } from 'react'

interface Props {
  isOpen:       boolean
  onClose:      () => void
  title?:       string
  subtitle?:    string
  icon?:        React.ReactNode
  maxWidth?:    number
  children:     React.ReactNode
  footer?:      React.ReactNode
  closeOnBackdrop?: boolean
}

export default function Modal({
  isOpen, onClose, title, subtitle, icon, maxWidth = 480,
  children, footer, closeOnBackdrop = true,
}: Props) {
  // Close on Escape key
  useEffect(() => {
    if (!isOpen) return
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [isOpen, onClose])

  // Prevent body scroll when open
  useEffect(() => {
    document.body.style.overflow = isOpen ? 'hidden' : ''
    return () => { document.body.style.overflow = '' }
  }, [isOpen])

  if (!isOpen) return null

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem' }}>
      {/* Backdrop */}
      <div
        style={{ position: 'absolute', inset: 0, backgroundColor: 'rgba(15,23,42,0.5)', backdropFilter: 'blur(3px)' }}
        onClick={closeOnBackdrop ? onClose : undefined}
      />

      {/* Panel */}
      <div style={{
        position: 'relative', width: '100%', maxWidth,
        backgroundColor: '#fff', borderRadius: '1rem',
        boxShadow: '0 24px 80px rgba(0,0,0,0.18)',
        border: '1px solid #f1f5f9',
        overflow: 'hidden',
        display: 'flex', flexDirection: 'column',
        maxHeight: 'calc(100vh - 2rem)',
        animation: 'modal-in 180ms ease',
      }}>

        {/* Header */}
        {(title || icon) && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '1.1rem 1.25rem', borderBottom: '1px solid #f8fafc', flexShrink: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              {icon && (
                <div style={{ width: '32px', height: '32px', backgroundColor: '#f1f5f9', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                  {icon}
                </div>
              )}
              <div>
                {title && <h2 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0f172a', margin: 0 }}>{title}</h2>}
                {subtitle && <p style={{ fontSize: '0.75rem', color: '#94a3b8', margin: '2px 0 0' }}>{subtitle}</p>}
              </div>
            </div>
            <button
              onClick={onClose}
              style={{ width: '32px', height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '8px', border: 'none', backgroundColor: 'transparent', cursor: 'pointer', color: '#94a3b8', flexShrink: 0 }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>
        )}

        {/* Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '1.25rem' }}>
          {children}
        </div>

        {/* Footer */}
        {footer && (
          <div style={{ borderTop: '1px solid #f8fafc', padding: '1rem 1.25rem', flexShrink: 0 }}>
            {footer}
          </div>
        )}
      </div>

      <style>{`
        @keyframes modal-in {
          from { opacity: 0; transform: scale(0.96) translateY(8px); }
          to   { opacity: 1; transform: scale(1)    translateY(0); }
        }
      `}</style>
    </div>
  )
}
