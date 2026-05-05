import { useState } from 'react'
import { toast } from 'react-hot-toast'
import { usersApi } from '@/api/users.api'
import { getErrorMessage } from '@/api/client'
import { ROLE_LABELS, ROLE_COLORS } from '@/utils/permissions'
import { formatDate } from '@/utils/formatters'
import ConfirmDialog from '@/components/ui/ConfirmDialog'
import type { User, RoleName } from '@/types/user.types'

interface Props {
  users:     User[]
  loading:   boolean
  onEdit:    (user: User) => void
  onRefresh: () => void
}

export default function UserTable({ users, loading, onEdit, onRefresh }: Props) {
  const [deactivating, setDeactivating] = useState<User | null>(null)
  const [deleting, setDeleting]         = useState<User | null>(null)
  const [actionLoading, setActionLoading] = useState(false)

  const handleDeactivate = async () => {
    if (!deactivating) return
    setActionLoading(true)
    try {
      await usersApi.deactivate(deactivating.id)
      toast.success(`${deactivating.full_name} deactivated`)
      onRefresh()
      setDeactivating(null)
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setActionLoading(false)
    }
  }

  const handleDelete = async () => {
    if (!deleting) return
    setActionLoading(true)
    try {
      await usersApi.delete(deleting.id)
      toast.success(`${deleting.full_name} deleted`)
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
        {[...Array(5)].map((_, i) => (
          <div key={i} style={{ height: '56px', backgroundColor: 'var(--bg)', borderRadius: '8px', animation: 'pulse 1.5s ease infinite' }} />
        ))}
        <style>{`@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.5}}`}</style>
      </div>
    )
  }

  if (users.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-tertiary)' }}>
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ margin: '0 auto 0.75rem', display: 'block' }}>
          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>
          <path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>
        </svg>
        <p style={{ fontWeight: 600, margin: 0 }}>No users found</p>
      </div>
    )
  }

  return (
    <>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              {['User', 'Email', 'Roles', 'Status', 'Joined', 'Actions'].map((h) => (
                <th key={h} style={{ padding: '0.625rem 1rem', textAlign: 'left', fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.06em', whiteSpace: 'nowrap' }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {users.map((user) => {
              const initials = user.full_name.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2)
              return (
                <tr key={user.id} style={{ borderBottom: '1px solid var(--border)' }}
                  onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--bg)')}
                  onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                >
                  {/* User */}
                  <td style={{ padding: '0.75rem 1rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <div style={{ width: '34px', height: '34px', borderRadius: '50%', backgroundColor: 'var(--text)', color: 'var(--surface)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.72rem', fontWeight: 700, flexShrink: 0 }}>
                        {initials}
                      </div>
                      <p style={{ fontWeight: 600, color: 'var(--text)', margin: 0, whiteSpace: 'nowrap' }}>
                        {user.full_name}
                      </p>
                    </div>
                  </td>
                  {/* Email */}
                  <td style={{ padding: '0.75rem 1rem', color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>
                    {user.email}
                  </td>
                  {/* Roles */}
                  <td style={{ padding: '0.75rem 1rem' }}>
                    <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                      {user.roles.map((role) => (
                        <span key={role.id} style={{ fontSize: '0.68rem', fontWeight: 600, padding: '2px 7px', borderRadius: '999px', ...getRoleBadge(role.name as RoleName) }}>
                          {ROLE_LABELS[role.name as RoleName] ?? role.name}
                        </span>
                      ))}
                    </div>
                  </td>
                  {/* Status */}
                  <td style={{ padding: '0.75rem 1rem' }}>
                    <span style={{ fontSize: '0.72rem', fontWeight: 600, padding: '3px 8px', borderRadius: '999px', backgroundColor: user.is_active ? '#f0fdf4' : '#fef2f2', color: user.is_active ? '#16a34a' : '#dc2626' }}>
                      {user.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  {/* Joined */}
                  <td style={{ padding: '0.75rem 1rem', color: 'var(--text-tertiary)', whiteSpace: 'nowrap', fontSize: '0.78rem' }}>
                    {formatDate(user.created_at)}
                  </td>
                  {/* Actions */}
                  <td style={{ padding: '0.75rem 1rem' }}>
                    <div style={{ display: 'flex', gap: '4px' }}>
                      <ActionBtn onClick={() => onEdit(user)} title="Edit" color="#475569">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                      </ActionBtn>
                      {user.is_active && (
                        <ActionBtn onClick={() => setDeactivating(user)} title="Deactivate" color="#d97706">
                          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/></svg>
                        </ActionBtn>
                      )}
                      <ActionBtn onClick={() => setDeleting(user)} title="Delete" color="#dc2626">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>
                      </ActionBtn>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <ConfirmDialog
        isOpen={!!deactivating}
        title="Deactivate user"
        message={`Deactivate "${deactivating?.full_name}"? They will no longer be able to log in.`}
        confirmLabel="Deactivate"
        loading={actionLoading}
        onConfirm={handleDeactivate}
        onCancel={() => setDeactivating(null)}
      />
      <ConfirmDialog
        isOpen={!!deleting}
        title="Delete user"
        message={`Permanently delete "${deleting?.full_name}"? This cannot be undone.`}
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

function getRoleBadge(name: RoleName): React.CSSProperties {
  const map: Record<string, React.CSSProperties> = {
    admin:   { backgroundColor: '#f3e8ff', color: '#7c3aed' },
    maker:   { backgroundColor: '#dbeafe', color: '#1d4ed8' },
    checker: { backgroundColor: '#ffedd5', color: '#c2410c' },
    auditor: { backgroundColor: '#dcfce7', color: '#15803d' },
  }
  return map[name] ?? { backgroundColor: 'var(--surface-2)', color: 'var(--text-secondary)' }
}
