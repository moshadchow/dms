import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'react-hot-toast'
import { usersApi } from '@/api/users.api'
import { useAuthStore } from '@/store/authStore'
import { getErrorMessage } from '@/api/client'
import UserTable from '@/components/admin/UserTable'
import UserFormModal from '@/components/admin/UserFormModal'
import PermissionMatrix from '@/components/admin/PermissionMatrix'
import type { User, Role, Permission } from '@/types/user.types'

type Tab = 'users' | 'roles' | 'permissions'

export default function AdminPage() {
  const navigate    = useNavigate()
  const { isAdmin } = useAuthStore()

  // Redirect non-admins
  useEffect(() => {
    if (!isAdmin()) { navigate('/dashboard', { replace: true }) }
  }, [])

  const [activeTab, setActiveTab]   = useState<Tab>('users')
  const [users, setUsers]           = useState<User[]>([])
  const [roles, setRoles]           = useState<Role[]>([])
  const [permissions, setPermissions] = useState<Permission[]>([])
  const [loadingUsers, setLoadingUsers] = useState(true)
  const [loadingRoles, setLoadingRoles] = useState(true)
  const [search, setSearch]         = useState('')
  const [filterActive, setFilterActive] = useState<string>('')
  const [formOpen, setFormOpen]     = useState(false)
  const [editingUser, setEditingUser] = useState<User | null>(null)
  const [userPage, setUserPage]     = useState(1)
  const [totalUsers, setTotalUsers] = useState(0)
  const LIMIT = 20

  const loadUsers = useCallback(async () => {
    setLoadingUsers(true)
    try {
      const data = await usersApi.list({
        skip:      (userPage - 1) * LIMIT,
        limit:     LIMIT,
        search:    search.trim() || undefined,
        is_active: filterActive === '' ? undefined : filterActive === 'true',
      })
      setUsers(data.items)
      setTotalUsers(data.total)
    } catch {
      toast.error('Failed to load users')
    } finally {
      setLoadingUsers(false)
    }
  }, [userPage, search, filterActive])

  const loadRoles = useCallback(async () => {
    setLoadingRoles(true)
    try {
      const [r, p] = await Promise.all([usersApi.listRoles(), usersApi.listPermissions()])
      setRoles(r)
      setPermissions(p)
    } catch {
      toast.error('Failed to load roles')
    } finally {
      setLoadingRoles(false)
    }
  }, [])

  useEffect(() => { loadUsers() }, [loadUsers])
  useEffect(() => { loadRoles() }, [loadRoles])
  useEffect(() => { setUserPage(1) }, [search, filterActive])

  const totalPages = Math.ceil(totalUsers / LIMIT) || 1

  const tabs: { id: Tab; label: string; icon: React.ReactNode }[] = [
    {
      id: 'users', label: 'Users',
      icon: <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>,
    },
    {
      id: 'roles', label: 'Roles & Permissions',
      icon: <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>,
    },
  ]

  return (
    <div>
      {/* Page header */}
      <div style={{ backgroundColor: 'var(--surface)', borderRadius: '1rem', border: '1px solid var(--border)', padding: '1.25rem 1.5rem', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text)', margin: 0 }}>Admin Panel</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.82rem', margin: '3px 0 0' }}>
            Manage users, roles, and system permissions
          </p>
        </div>
        {activeTab === 'users' && (
          <button
            onClick={() => { setEditingUser(null); setFormOpen(true) }}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '7px 14px', backgroundColor: 'var(--text)', color: 'var(--surface)', border: 'none', borderRadius: '8px', fontSize: '0.85rem', fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            New user
          </button>
        )}
      </div>

      {/* Stats row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '0.75rem', marginBottom: '1.25rem' }}>
        {[
          { label: 'Total users', value: totalUsers, color: 'var(--primary)', icon: '👥' },
          { label: 'Active users', value: users.filter((u) => u.is_active).length, color: 'var(--success)', icon: '✅' },
          { label: 'Roles', value: roles.length, color: 'var(--warning)', icon: '🔐' },
          { label: 'Permissions', value: permissions.length, color: 'var(--info)', icon: '⚙️' },
        ].map((s) => (
          <div key={s.label} style={{ backgroundColor: 'var(--surface)', borderRadius: '0.875rem', border: '1px solid var(--border)', padding: '1rem 1.125rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <p style={{ fontSize: '1.4rem', fontWeight: 700, color: s.color, margin: 0 }}>{s.value}</p>
              <span style={{ fontSize: '1.25rem' }}>{s.icon}</span>
            </div>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', margin: '2px 0 0', fontWeight: 500 }}>{s.label}</p>
          </div>
        ))}
      </div>

      {/* Main card */}
      <div style={{ backgroundColor: 'var(--surface)', borderRadius: '1rem', border: '1px solid var(--border)', overflow: 'hidden' }}>

        {/* Tabs */}
        <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', padding: '0 1.25rem' }}>
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                display: 'flex', alignItems: 'center', gap: '7px',
                padding: '0.875rem 1rem',
                border: 'none', borderBottom: `2px solid ${activeTab === tab.id ? '#4f46e5' : 'transparent'}`,
                backgroundColor: 'transparent', cursor: 'pointer', fontFamily: 'inherit',
                fontSize: '0.85rem', fontWeight: activeTab === tab.id ? 700 : 500,
                color: activeTab === tab.id ? '#4f46e5' : 'var(--text-secondary)',
                transition: 'all 150ms', marginBottom: '-1px',
              }}
            >
              {tab.icon}{tab.label}
            </button>
          ))}
        </div>

        {/* ── Users tab ── */}
        {activeTab === 'users' && (
          <>
            {/* Toolbar */}
            <div style={{ padding: '1rem 1.25rem', borderBottom: '1px solid var(--border)', display: 'flex', gap: '0.625rem', flexWrap: 'wrap' }}>
              <div style={{ flex: 1, minWidth: '200px', position: 'relative' }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2" style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)' }}>
                  <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
                </svg>
                <input className="input" placeholder="Search by name or email…" value={search} onChange={(e) => setSearch(e.target.value)} style={{ paddingLeft: '32px', fontSize: '0.82rem' }} />
              </div>
              <select className="input" value={filterActive} onChange={(e) => setFilterActive(e.target.value)} style={{ width: '140px', fontSize: '0.82rem' }}>
                <option value="">All status</option>
                <option value="true">Active only</option>
                <option value="false">Inactive only</option>
              </select>
            </div>

            <UserTable
              users={users}
              loading={loadingUsers}
              onEdit={(u) => { setEditingUser(u); setFormOpen(true) }}
              onRefresh={loadUsers}
            />

            {/* Pagination */}
            {totalPages > 1 && (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', padding: '1rem', borderTop: '1px solid var(--border)' }}>
                <button onClick={() => setUserPage((p) => Math.max(1, p - 1))} disabled={userPage === 1} style={pageBtn}>←</button>
                <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>Page {userPage} of {totalPages}</span>
                <button onClick={() => setUserPage((p) => Math.min(totalPages, p + 1))} disabled={userPage === totalPages} style={pageBtn}>→</button>
              </div>
            )}
          </>
        )}

        {/* ── Roles & Permissions tab ── */}
        {activeTab === 'roles' && (
          <div style={{ padding: '1.25rem' }}>
            <div style={{ marginBottom: '1.5rem' }}>
              <h3 style={{ fontSize: '0.875rem', fontWeight: 700, color: 'var(--text)', margin: '0 0 0.25rem' }}>
                Role Permission Matrix
              </h3>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)', margin: 0 }}>
                Overview of what each role can do in the system.
              </p>
            </div>

            {loadingRoles ? (
              <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem' }}>
                <div style={{ width: '24px', height: '24px', border: '3px solid #e2e8f0', borderTopColor: '#4f46e5', borderRadius: '50%', animation: 'spin 0.7s linear infinite' }} />
                <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
              </div>
            ) : (
              <div style={{ backgroundColor: 'var(--bg)', borderRadius: '0.75rem', border: '1px solid var(--border)', overflow: 'hidden' }}>
                <PermissionMatrix roles={roles} />
              </div>
            )}

            {/* Individual role cards */}
            {!loadingRoles && (
              <div style={{ marginTop: '1.5rem' }}>
                <h3 style={{ fontSize: '0.875rem', fontWeight: 700, color: 'var(--text)', margin: '0 0 0.875rem' }}>Role details</h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '0.75rem' }}>
                  {roles.map((role) => (
                    <div key={role.id} style={{ backgroundColor: 'var(--bg)', borderRadius: '0.75rem', border: '1px solid var(--border)', padding: '0.875rem' }}>
                      <p style={{ fontWeight: 700, color: 'var(--text)', margin: '0 0 0.25rem', fontSize: '0.875rem' }}>
                        {role.name.charAt(0).toUpperCase() + role.name.slice(1)}
                      </p>
                      {role.description && (
                        <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', margin: '0 0 0.625rem', lineHeight: 1.5 }}>
                          {role.description}
                        </p>
                      )}
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                        {role.permissions.map((p) => (
                          <span key={p.id} style={{ fontSize: '0.65rem', fontWeight: 600, padding: '2px 6px', borderRadius: '999px', backgroundColor: 'var(--primary-soft)', color: '#4338ca' }}>
                            {p.action}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* User form modal */}
      <UserFormModal
        isOpen={formOpen}
        editing={editingUser}
        roles={roles}
        onClose={() => { setFormOpen(false); setEditingUser(null) }}
        onSuccess={loadUsers}
      />
    </div>
  )
}

const pageBtn: React.CSSProperties = {
  padding: '5px 12px', borderRadius: '7px', border: '1px solid var(--border-soft)',
  backgroundColor: 'var(--surface)', color: 'var(--text-secondary)', fontSize: '0.82rem',
  cursor: 'pointer', fontFamily: 'inherit',
}
