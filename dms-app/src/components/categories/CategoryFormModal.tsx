import { useState, useEffect } from 'react'
import { toast } from 'react-hot-toast'
import { categoriesApi } from '@/api/categories.api'
import { getErrorMessage } from '@/api/client'
import type { Category } from '@/types/category.types'

interface Props {
  isOpen:    boolean
  onClose:   () => void
  onSuccess: (cat: Category) => void
  editing?:  Category | null
}

export default function CategoryFormModal({ isOpen, onClose, onSuccess, editing }: Props) {
  const [name, setName]         = useState('')
  const [description, setDesc]  = useState('')
  const [isActive, setIsActive] = useState(true)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState('')

  useEffect(() => {
    if (editing) {
      setName(editing.name)
      setDesc(editing.description ?? '')
      setIsActive(editing.is_active)
    } else {
      setName('')
      setDesc('')
      setIsActive(true)
    }
    setError('')
  }, [editing, isOpen])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) { setError('Category name is required.'); return }
    setLoading(true)
    setError('')
    try {
      let result: Category
      if (editing) {
        result = await categoriesApi.update(editing.id, {
          name: name.trim(),
          description: description.trim() || undefined,
          is_active: isActive,
        })
        toast.success('Category updated')
      } else {
        result = await categoriesApi.create({
          name: name.trim(),
          description: description.trim() || undefined,
          is_active: isActive,
        })
        toast.success('Category created')
      }
      onSuccess(result)
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
      <div style={{ position: 'relative', width: '100%', maxWidth: '440px', backgroundColor: 'var(--surface)', borderRadius: '1rem', boxShadow: '0 20px 60px rgba(0,0,0,0.15)', border: '1px solid var(--border)', overflow: 'hidden' }}>

        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '1.1rem 1.25rem', borderBottom: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ width: '32px', height: '32px', backgroundColor: 'var(--surface-2)', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#4f46e5" strokeWidth="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
            </div>
            <h2 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text)', margin: 0 }}>
              {editing ? 'Edit category' : 'New category'}
            </h2>
          </div>
          <button onClick={onClose} style={{ width: '32px', height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '8px', border: 'none', backgroundColor: 'transparent', cursor: 'pointer', color: 'var(--text-tertiary)' }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} style={{ padding: '1.25rem' }}>
          {error && (
            <div style={{ marginBottom: '1rem', padding: '0.75rem', backgroundColor: 'var(--danger-bg)', border: '1px solid var(--danger)', borderRadius: '0.5rem', color: 'var(--danger)', fontSize: '0.85rem' }}>
              {error}
            </div>
          )}

          <div style={{ marginBottom: '1rem' }}>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
              Name <span style={{ color: '#ef4444' }}>*</span>
            </label>
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Finance, Human Resources" disabled={loading} autoFocus />
          </div>

          <div style={{ marginBottom: '1rem' }}>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>Description</label>
            <textarea className="input" value={description} onChange={(e) => setDesc(e.target.value)} placeholder="Optional description..." disabled={loading} rows={3} style={{ resize: 'vertical', fontFamily: 'inherit' }} />
          </div>

          {editing && (
            <div style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '10px' }}>
              <button type="button" onClick={() => setIsActive(!isActive)} style={{ width: '40px', height: '22px', borderRadius: '999px', border: 'none', backgroundColor: isActive ? '#4f46e5' : 'var(--surface-3)', cursor: 'pointer', position: 'relative', transition: 'background 200ms', flexShrink: 0 }}>
                <span style={{ position: 'absolute', top: '3px', left: isActive ? '21px' : '3px', width: '16px', height: '16px', backgroundColor: 'var(--surface)', borderRadius: '50%', transition: 'left 200ms', boxShadow: '0 1px 3px rgba(0,0,0,0.2)' }} />
              </button>
              <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', fontWeight: 500 }}>{isActive ? 'Active' : 'Inactive'}</span>
            </div>
          )}

          <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1.25rem' }}>
            <button type="button" onClick={onClose} disabled={loading} style={{ flex: 1, padding: '0.625rem', backgroundColor: 'var(--bg)', color: 'var(--text-secondary)', border: '1px solid var(--border-soft)', borderRadius: '0.5rem', fontSize: '0.875rem', fontWeight: 500, cursor: 'pointer', fontFamily: 'inherit' }}>
              Cancel
            </button>
            <button type="submit" disabled={loading} style={{ flex: 1, padding: '0.625rem', backgroundColor: 'var(--text)', color: 'var(--surface)', border: 'none', borderRadius: '0.5rem', fontSize: '0.875rem', fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}>
              {loading ? <><span style={{ width: '14px', height: '14px', border: '2px solid rgba(255,255,255,0.3)', borderTopColor: 'var(--surface)', borderRadius: '50%', animation: 'spin 0.7s linear infinite', display: 'inline-block' }} />Saving…</> : (editing ? 'Save changes' : 'Create category')}
            </button>
          </div>
        </form>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    </div>
  )
}
