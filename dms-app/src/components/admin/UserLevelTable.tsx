import { useState } from 'react'
import { toast } from 'react-hot-toast'
import { usersApi } from '@/api/users.api'
import { getErrorMessage } from '@/api/client'
import { formatDate } from '@/utils/formatters'
import ConfirmDialog from '@/components/ui/ConfirmDialog'
import type { UserLevel } from '@/types/user.types'

interface Props {
  levels:    UserLevel[]
  loading:   boolean
  onEdit:    (level: UserLevel) => void
  onRefresh: () => void
}

export default function UserLevelTable({ levels, loading, onEdit, onRefresh }: Props) {
  const [deleting, setDeleting]       = useState<UserLevel | null>(null)
  const [actionLoading, setActionLoading] = useState(false)

  const handleDelete = async () => {
    if (!deleting) return
    setActionLoading(true)
    try {
      await usersApi.deleteUserLevel(deleting.id)
      toast.success(`"${deleting.name}" deleted`)
      onRefresh()
      setDeleting(null)
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setActionLoading(false)
    }
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        {[...Array(3)].map((_, i) => (
          <div key={i} style={{ height: '56px', backgroundColor: 'var(--bg)', borderRadius: '8px', animation: 'pulse 1.5s ease infinite' }} />
        ))}
        <style>{`@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.5}}`}</style>
      </div>
    )
  }

  if (levels.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-tertiary)' }}>
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ margin: '0 auto 0.75rem', display: 'block' }}>
          <path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>
        </svg>
        <p style={{ fontWeight: 600, margin: 0 }}>No user levels configured</p>
      </div>
    )
  }

  return (
    <>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              {['Name', 'Description', 'Status', 'Created', 'Actions'].map((h) => (
                <th key={h} style={{ padding: '0.625rem 1rem', textAlign: 'left', fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.06em', whiteSpace: 'nowrap' }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {levels.map((level) => (
              <tr key={level.id} style={{ borderBottom: '1px solid var(--border)' }}
                onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--bg)')}
                onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
              >
                <td style={{ padding: '0.75rem 1rem' }}>
                  <p style={{ fontWeight: 600, color: 'var(--text)', margin: 0 }}>{level.name}</p>
                </td>
                <td style={{ padding: '0.75rem 1rem', color: 'var(--text-secondary)' }}>
                  {level.description || '—'}
                </td>
                <td style={{ padding: '0.75rem 1rem' }}>
                  <span style={{ fontSize: '0.72rem', fontWeight: 600, padding: '3px 8px', borderRadius: '999px', backgroundColor: level.is_active ? '#f0fdf4' : '#fef2f2', color: level.is_active ? '#16a34a' : '#dc2626' }}>
                    {level.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td style={{ padding: '0.75rem 1rem', color: 'var(--text-tertiary)', whiteSpace: 'nowrap', fontSize: '0.78rem' }}>
                  {formatDate(level.created_at)}
                </td>
                <td style={{ padding: '0.75rem 1rem' }}>
                  <div style={{ display: 'flex', gap: '4px' }}>
                    <ActionBtn onClick={() => onEdit(level)} title="Edit" color="#475569">
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                    </ActionBtn>
                    <ActionBtn onClick={() => setDeleting(level)} title="Delete" color="#dc2626">
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>
                    </ActionBtn>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ConfirmDialog
        isOpen={!!deleting}
        title="Delete user level"
        message={`Permanently delete "${deleting?.name}"? This cannot be undone.`}
        confirmLabel="Delete"
        danger
        loading={actionLoading}
        onConfirm={handleDelete}
        onCancel={() => setDeleting(null)}
      />
    </>
  )
}

function ActionBtn({ onClick, title, color, children }: { onClick: () => void; title: string; color: string; children: React.ReactNode }) {
  return (
    <button onClick={onClick} title={title} style={{ width: '28px', height: '28px', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '6px', border: 'none', backgroundColor: 'var(--bg)', cursor: 'pointer', color }}>
      {children}
    </button>
  )
}
