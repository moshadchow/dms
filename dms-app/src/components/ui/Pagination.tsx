interface Props {
  page:     number
  total:    number
  limit:    number
  onChange: (page: number) => void
}

export default function Pagination({ page, total, limit, onChange }: Props) {
  const totalPages = Math.ceil(total / limit) || 1
  if (totalPages <= 1) return null

  const start = (page - 1) * limit + 1
  const end   = Math.min(page * limit, total)

  // Build page numbers to show (always show first, last, current ±1)
  const pages: (number | '...')[] = []
  for (let i = 1; i <= totalPages; i++) {
    if (i === 1 || i === totalPages || (i >= page - 1 && i <= page + 1)) {
      pages.push(i)
    } else if (pages[pages.length - 1] !== '...') {
      pages.push('...')
    }
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.75rem', flexWrap: 'wrap' }}>
      <p style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)', margin: 0 }}>
        Showing <strong style={{ color: 'var(--text-secondary)' }}>{start}–{end}</strong> of <strong style={{ color: 'var(--text-secondary)' }}>{total}</strong>
      </p>

      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
        <PageBtn onClick={() => onChange(page - 1)} disabled={page === 1}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"/></svg>
        </PageBtn>

        {pages.map((p, i) =>
          p === '...' ? (
            <span key={`dot-${i}`} style={{ padding: '0 4px', color: 'var(--text-tertiary)', fontSize: '0.82rem' }}>…</span>
          ) : (
            <PageBtn key={p} onClick={() => onChange(p as number)} active={p === page}>
              {p}
            </PageBtn>
          )
        )}

        <PageBtn onClick={() => onChange(page + 1)} disabled={page === totalPages}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="9 18 15 12 9 6"/></svg>
        </PageBtn>
      </div>
    </div>
  )
}

function PageBtn({ children, onClick, disabled, active }: {
  children: React.ReactNode
  onClick:  () => void
  disabled?: boolean
  active?:   boolean
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        minWidth: '32px', height: '32px',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        borderRadius: '7px', border: '1px solid',
        borderColor: active ? '#4f46e5' : 'var(--surface-3)',
        backgroundColor: active ? '#4f46e5' : 'var(--surface)',
        color: active ? 'var(--surface)' : disabled ? 'var(--text-muted)' : 'var(--text-secondary)',
        fontSize: '0.82rem', fontWeight: active ? 700 : 500,
        cursor: disabled ? 'not-allowed' : 'pointer',
        fontFamily: 'inherit', padding: '0 6px',
      }}
    >
      {children}
    </button>
  )
}
