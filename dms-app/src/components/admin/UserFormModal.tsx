import { useState, useEffect } from 'react'
import { toast } from 'react-hot-toast'
import { usersApi } from '@/api/users.api'
import { getErrorMessage } from '@/api/client'
import { ROLE_LABELS } from '@/utils/permissions'
import type { User, Role, RoleName } from '@/types/user.types'

interface Props {
  isOpen:    boolean
  onClose:   () => void
  onSuccess: () => void
  editing?:  User | null
  roles:     Role[]
}

export default function UserFormModal({ isOpen, onClose, onSuccess, editing, roles }: Props) {
  const [fullName, setFullName]     = useState('')
  const [email, setEmail]           = useState('')
  const [password, setPassword]     = useState('')
  const [isActive, setIsActive]     = useState(true)
  const [selectedRoles, setSelectedRoles] = useState<number[]>([])
  const [loading, setLoading]       = useState(false)
  const [error, setError]           = useState('')

  useEffect(() => {
    if (editing) {
      setFullName(editing.full_name)
      setEmail(editing.email)
      setIsActive(editing.is_active)
      setSelectedRoles(editing.roles.map((r) => r.id))
      setPassword('')
    } else {
      setFullName('')
      setEmail('')
      setPassword('')
      setIsActive(true)
      setSelectedRoles([])
    }
    setError('')
  }, [editing, isOpen])

  const toggleRole = (id: number) => {
    setSelectedRoles((prev) =>
      prev.includes(id) ? prev.filter((r) => r !== id) : [...prev, id]
    )
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!fullName.trim())         { setError('Full name is required.'); return }
    if (!email.trim())            { setError('Email is required.'); return }
    if (!editing && !password)    { setError('Password is required for new users.'); return }
    if (selectedRoles.length === 0) { setError('Assign at least one role.'); return }

    setLoading(true)
    setError('')
    try {
      if (editing) {
        await usersApi.update(editing.id, {
          full_name: fullName.trim(),
          email:     email.trim(),
          is_active: isActive,
          role_ids:  selectedRoles,
        })
        toast.success('User updated')
      } else {
        await usersApi.create({
          full_name: fullName.trim(),
          email:     email.trim(),
          password,
          is_active: isActive,
          role_ids:  selectedRoles,
        })
        toast.success('User created')
      }
      onSuccess()
      onClose()
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null

  const roleColors: Record<string, { bg: string; border: string; active: string; text: string }> = {
    admin:   { bg: '#faf5ff', border: '#e9d5ff', active: '#7c3aed', text: '#6d28d9' },
    maker:   { bg: '#eff6ff', border: '#bfdbfe', active: '#2563eb', text: '#1d4ed8' },
    checker: { bg: '#fff7ed', border: '#fed7aa', active: '#ea580c', text: '#c2410c' },
    auditor: { bg: '#f0fdf4', border: '#bbf7d0', active: '#16a34a', text: '#15803d' },
  }

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem' }}>
      <div style={{ position: 'absolute', inset: 0, backgroundColor: 'rgba(15,23,42,0.45)', backdropFilter: 'blur(2px)' }} onClick={onClose} />
      <div style={{ position: 'relative', width: '100%', maxWidth: '480px', backgroundColor: 'var(--surface)', borderRadius: '1rem', boxShadow: '0 20px 60px rgba(0,0,0,0.15)', border: '1px solid var(--border)', overflow: 'hidden', maxHeight: '90vh', display: 'flex', flexDirection: 'column' }}>

        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '1.1rem 1.25rem', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ width: '32px', height: '32px', backgroundColor: 'var(--surface-2)', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#475569" strokeWidth="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
            </div>
            <h2 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text)', margin: 0 }}>
              {editing ? 'Edit user' : 'New user'}
            </h2>
          </div>
          <button onClick={onClose} style={{ width: '32px', height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '8px', border: 'none', backgroundColor: 'transparent', cursor: 'pointer', color: 'var(--text-tertiary)' }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} style={{ padding: '1.25rem', overflowY: 'auto', flex: 1 }}>
          {error && (
            <div style={{ marginBottom: '1rem', padding: '0.75rem', backgroundColor: '#fef2f2', border: '1px solid #fecaca', borderRadius: '0.5rem', color: '#dc2626', fontSize: '0.85rem' }}>
              {error}
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
            <div>
              <label style={labelStyle}>Full name <Req /></label>
              <input className="input" value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Jane Doe" disabled={loading} autoFocus />
            </div>
            <div>
              <label style={labelStyle}>Email <Req /></label>
              <input className="input" type="text" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="jane@company.com" disabled={loading} />
            </div>
          </div>

          {!editing && (
            <div style={{ marginBottom: '0.75rem' }}>
              <label style={labelStyle}>Password <Req /></label>
              <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Min 8 chars, 1 uppercase, 1 digit" disabled={loading} />
            </div>
          )}

          {/* Active toggle */}
          {editing && (
            <div style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '10px' }}>
              <button type="button" onClick={() => setIsActive(!isActive)} style={{ width: '40px', height: '22px', borderRadius: '999px', border: 'none', backgroundColor: isActive ? '#4f46e5' : 'var(--surface-3)', cursor: 'pointer', position: 'relative', transition: 'background 200ms', flexShrink: 0 }}>
                <span style={{ position: 'absolute', top: '3px', left: isActive ? '21px' : '3px', width: '16px', height: '16px', backgroundColor: 'var(--surface)', borderRadius: '50%', transition: 'left 200ms', boxShadow: '0 1px 3px rgba(0,0,0,0.2)' }} />
              </button>
              <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', fontWeight: 500 }}>{isActive ? 'Active account' : 'Inactive account'}</span>
            </div>
          )}

          {/* Role selection */}
          <div style={{ marginBottom: '1.25rem' }}>
            <label style={{ ...labelStyle, marginBottom: '0.6rem' }}>Roles <Req /></label>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
              {roles.map((role) => {
                const c       = roleColors[role.name] ?? roleColors.auditor
                const checked = selectedRoles.includes(role.id)
                return (
                  <button
                    key={role.id}
                    type="button"
                    onClick={() => toggleRole(role.id)}
                    style={{
                      display: 'flex', alignItems: 'center', gap: '8px',
                      padding: '8px 10px', borderRadius: '8px',
                      border: `1.5px solid ${checked ? c.active : c.border}`,
                      backgroundColor: checked ? c.bg : 'var(--surface)',
                      cursor: 'pointer', textAlign: 'left', fontFamily: 'inherit',
                      transition: 'all 150ms',
                    }}
                  >
                    <div style={{ width: '16px', height: '16px', borderRadius: '4px', border: `2px solid ${checked ? c.active : 'var(--surface-3)'}`, backgroundColor: checked ? c.active : 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, transition: 'all 150ms' }}>
                      {checked && <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3"><polyline points="20 6 9 17 4 12"/></svg>}
                    </div>
                    <div>
                      <p style={{ fontSize: '0.82rem', fontWeight: 600, color: checked ? c.text : 'var(--text-secondary)', margin: 0 }}>
                        {ROLE_LABELS[role.name as RoleName] ?? role.name}
                      </p>
                      <p style={{ fontSize: '0.68rem', color: 'var(--text-tertiary)', margin: '1px 0 0' }}>
                        {role.permissions.length} permissions
                      </p>
                    </div>
                  </button>
                )
              })}
            </div>
          </div>

          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <button type="button" onClick={onClose} disabled={loading} style={{ flex: 1, padding: '0.625rem', backgroundColor: 'var(--bg)', color: 'var(--text-secondary)', border: '1px solid var(--border-soft)', borderRadius: '0.5rem', fontSize: '0.875rem', fontWeight: 500, cursor: 'pointer', fontFamily: 'inherit' }}>
              Cancel
            </button>
            <button type="submit" disabled={loading} style={{ flex: 1, padding: '0.625rem', backgroundColor: 'var(--text)', color: 'var(--surface)', border: 'none', borderRadius: '0.5rem', fontSize: '0.875rem', fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}>
              {loading ? <><Spin />Saving…</> : editing ? 'Save changes' : 'Create user'}
            </button>
          </div>
        </form>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    </div>
  )
}

const labelStyle: React.CSSProperties = { display: 'block', fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.35rem' }
const Req = () => <span style={{ color: '#ef4444' }}> *</span>
const Spin = () => <span style={{ width: '14px', height: '14px', border: '2px solid rgba(255,255,255,0.3)', borderTopColor: 'var(--surface)', borderRadius: '50%', animation: 'spin 0.7s linear infinite', display: 'inline-block' }} />
