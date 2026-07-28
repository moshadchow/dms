import { useState, useEffect } from 'react'
import { toast } from 'react-hot-toast'
import { usersApi } from '@/api/users.api'
import { getErrorMessage } from '@/api/client'
import type { UserLevel } from '@/types/user.types'

interface Props {
  isOpen:    boolean
  onClose:   () => void
  onSuccess: () => void
  editing?:  UserLevel | null
}

export default function UserLevelFormModal({ isOpen, onClose, onSuccess, editing }: Props) {
  const [name, setName]             = useState('')
  const [description, setDescription] = useState('')
  const [isActive, setIsActive]     = useState(true)
  const [loading, setLoading]       = useState(false)
  const [error, setError]           = useState('')

  useEffect(() => {
    if (editing) {
      setName(editing.name)
      setDescription(editing.description || '')
      setIsActive(editing.is_active)
    } else {
      setName('')
      setDescription('')
      setIsActive(true)
    }
    setError('')
  }, [editing, isOpen])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) { setError('Name is required.'); return }

    setLoading(true)
    setError('')
    try {
      if (editing) {
        await usersApi.updateUserLevel(editing.id, {
          name:        name.trim(),
          description: description.trim() || undefined,
          is_active:   isActive,
        })
        toast.success('User level updated')
      } else {
        await usersApi.createUserLevel({
          name:        name.trim(),
          description: description.trim() || undefined,
          is_active:   isActive,
        })
        toast.success('User level created')
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

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem' }}>
      <div style={{ position: 'absolute', inset: 0, backgroundColor: 'rgba(15,23,42,0.45)', backdropFilter: 'blur(2px)' }} onClick={onClose} />
      <div style={{ position: 'relative', width: '100%', maxWidth: '420px', backgroundColor: 'var(--surface)', borderRadius: '1rem', boxShadow: '0 20px 60px rgba(0,0,0,0.15)', border: '1px solid var(--border)', overflow: 'hidden', maxHeight: '90vh', display: 'flex', flexDirection: 'column' }}>

        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '1.1rem 1.25rem', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ width: '32px', height: '32px', backgroundColor: 'var(--surface-2)', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#475569" strokeWidth="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
            </div>
            <h2 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text)', margin: 0 }}>
              {editing ? 'Edit user level' : 'New user level'}
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

          <div style={{ marginBottom: '0.75rem' }}>
            <label style={labelStyle}>Name <Req /></label>
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. High, Medium, Low" disabled={loading} autoFocus />
          </div>

          <div style={{ marginBottom: '0.75rem' }}>
            <label style={labelStyle}>Description</label>
            <textarea className="input" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Optional description" disabled={loading} rows={3} style={{ resize: 'vertical' }} />
          </div>

          {/* Active toggle */}
          <div style={{ marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <button type="button" onClick={() => setIsActive(!isActive)} style={{ width: '40px', height: '22px', borderRadius: '999px', border: 'none', backgroundColor: isActive ? '#4f46e5' : 'var(--surface-3)', cursor: 'pointer', position: 'relative', transition: 'background 200ms', flexShrink: 0 }}>
              <span style={{ position: 'absolute', top: '3px', left: isActive ? '21px' : '3px', width: '16px', height: '16px', backgroundColor: 'var(--surface)', borderRadius: '50%', transition: 'left 200ms', boxShadow: '0 1px 3px rgba(0,0,0,0.2)' }} />
            </button>
            <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', fontWeight: 500 }}>{isActive ? 'Active' : 'Inactive'}</span>
          </div>

          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <button type="button" onClick={onClose} disabled={loading} style={{ flex: 1, padding: '0.625rem', backgroundColor: 'var(--bg)', color: 'var(--text-secondary)', border: '1px solid var(--border-soft)', borderRadius: '0.5rem', fontSize: '0.875rem', fontWeight: 500, cursor: 'pointer', fontFamily: 'inherit' }}>
              Cancel
            </button>
            <button type="submit" disabled={loading} style={{ flex: 1, padding: '0.625rem', backgroundColor: 'var(--text)', color: 'var(--surface)', border: 'none', borderRadius: '0.5rem', fontSize: '0.875rem', fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}>
              {loading ? <><Spin />Saving…</> : editing ? 'Save changes' : 'Create level'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

const labelStyle: React.CSSProperties = { display: 'block', fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.35rem' }
const Req = () => <span style={{ color: '#ef4444' }}> *</span>
const Spin = () => <span style={{ width: '14px', height: '14px', border: '2px solid rgba(255,255,255,0.3)', borderTopColor: 'var(--surface)', borderRadius: '50%', animation: 'spin 0.7s linear infinite', display: 'inline-block' }} />
