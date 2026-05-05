import type { Category } from '@/types/category.types'

interface Props {
  category:  Category
  onClick:   () => void
  onEdit?:   () => void
  onDelete?: () => void
  isAdmin:   boolean
}

// Icon colors only — not backgrounds, those use CSS vars
const ICON_COLORS = [
  '#3b82f6', '#22c55e', '#a855f7',
  '#f97316', '#ef4444', '#14b8a6',
]

function getIconColor(name: string) {
  let sum = 0
  for (const c of name) sum += c.charCodeAt(0)
  return ICON_COLORS[sum % ICON_COLORS.length]
}

export default function CategoryCard({ category, onClick, onEdit, onDelete, isAdmin }: Props) {
  const iconColor = getIconColor(category.name)

  return (
    <div
      onClick={onClick}
      style={{
        backgroundColor: 'var(--surface)',
        borderRadius: '0.875rem',
        border: '1px solid var(--border)',
        padding: '1.25rem',
        cursor: 'pointer',
        transition: 'box-shadow 150ms, transform 150ms, border-color 150ms',
        position: 'relative',
        overflow: 'hidden',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.boxShadow = 'var(--shadow-md)'
        e.currentTarget.style.transform = 'translateY(-1px)'
        e.currentTarget.style.borderColor = 'var(--border-soft)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.boxShadow = 'none'
        e.currentTarget.style.transform = 'translateY(0)'
        e.currentTarget.style.borderColor = 'var(--border)'
      }}
    >
      {/* Inactive badge */}
      {!category.is_active && (
        <span style={{
          position: 'absolute', top: '0.75rem', right: '0.75rem',
          fontSize: '0.65rem', fontWeight: 600, padding: '2px 8px',
          borderRadius: '999px',
          backgroundColor: 'var(--warning-bg)',
          color: 'var(--warning)',
        }}>
          Inactive
        </span>
      )}

      {/* Icon */}
      <div style={{
        width: '40px', height: '40px', borderRadius: '10px',
        backgroundColor: 'var(--surface-2)',
        border: '1px solid var(--border-soft)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        marginBottom: '0.875rem',
      }}>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
          stroke={iconColor} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
        </svg>
      </div>

      {/* Name & description */}
      <p style={{ fontWeight: 700, fontSize: '0.95rem', color: 'var(--text)', margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {category.name}
      </p>
      {category.description && (
        <p style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)', margin: '4px 0 0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {category.description}
        </p>
      )}

      {/* Stats */}
      <div style={{ display: 'flex', gap: '1rem', marginTop: '0.875rem', paddingTop: '0.875rem', borderTop: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="2">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
          </svg>
          <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
            {category.directory_count ?? 0} dirs
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
          </svg>
          <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
            {category.document_count ?? 0} docs
          </span>
        </div>
      </div>

      {/* Admin actions */}
      {isAdmin && (
        <div style={{ display: 'flex', gap: '6px', marginTop: '0.75rem' }} onClick={(e) => e.stopPropagation()}>
          <button
            onClick={onEdit}
            style={{ flex: 1, padding: '5px', backgroundColor: 'var(--surface-2)', border: '1px solid var(--border-soft)', borderRadius: '6px', fontSize: '0.75rem', fontWeight: 500, color: 'var(--text-secondary)', cursor: 'pointer', fontFamily: 'inherit', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px' }}
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
            </svg>
            Edit
          </button>
          <button
            onClick={onDelete}
            style={{ flex: 1, padding: '5px', backgroundColor: 'var(--danger-bg)', border: '1px solid var(--danger)', borderRadius: '6px', fontSize: '0.75rem', fontWeight: 500, color: 'var(--danger)', cursor: 'pointer', fontFamily: 'inherit', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px' }}
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="3 6 5 6 21 6"/>
              <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
              <path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/>
            </svg>
            Delete
          </button>
        </div>
      )}
    </div>
  )
}
