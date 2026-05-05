import { useState, useEffect } from 'react'
import { toast } from 'react-hot-toast'
import { directoriesApi } from '@/api/directories.api'
import { getErrorMessage } from '@/api/client'
import type { Directory } from '@/types/directory.types'

interface Props {
  isOpen:      boolean
  onClose:     () => void
  onSuccess:   (dir: Directory) => void
  categoryId:  number
  parentId?:   number | null       // set when creating a subdirectory
  editing?:    Directory | null    // set when renaming
}

export default function DirectoryFormModal({
  isOpen, onClose, onSuccess, categoryId, parentId = null, editing,
}: Props) {
  const [name, setName]         = useState('')
  const [description, setDesc]  = useState('')
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState('')

  useEffect(() => {
    if (editing) {
      setName(editing.name)
      setDesc(editing.description ?? '')
    } else {
      setName('')
      setDesc('')
    }
    setError('')
  }, [editing, isOpen])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) { setError('Directory name is required.'); return }

    setLoading(true)
    setError('')
    try {
      let result: Directory
      if (editing) {
        result = await directoriesApi.update(editing.id, {
          name: name.trim(),
          description: description.trim() || undefined,
        })
        toast.success('Directory renamed')
      } else {
        result = await directoriesApi.create({
          name: name.trim(),
          description: description.trim() || undefined,
          category_id: categoryId,
          parent_id: parentId ?? null,
        })
        toast.success(parentId ? 'Subdirectory created' : 'Directory created')
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

  const title = editing
    ? 'Rename directory'
    : parentId
      ? 'New subdirectory'
      : 'New directory'

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem' }}>
      <div style={{ position: 'absolute', inset: 0, backgroundColor: 'rgba(15,23,42,0.45)', backdropFilter: 'blur(2px)' }} onClick={onClose} />
      <div style={{ position: 'relative', width: '100%', maxWidth: '420px', backgroundColor: 'var(--surface)', borderRadius: '1rem', boxShadow: '0 20px 60px rgba(0,0,0,0.15)', border: '1px solid var(--border)', overflow: 'hidden' }}>

        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '1.1rem 1.25rem', borderBottom: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ width: '32px', height: '32px', backgroundColor: 'var(--primary-soft)', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" strokeWidth="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
            </div>
            <h2 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text)', margin: 0 }}>{title}</h2>
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
            <input
              className="input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. 2024 Reports"
              disabled={loading}
              autoFocus
            />
          </div>

          <div style={{ marginBottom: '1rem' }}>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>Description</label>
            <input
              className="input"
              value={description}
              onChange={(e) => setDesc(e.target.value)}
              placeholder="Optional description"
              disabled={loading}
            />
          </div>

          {/* Parent context hint */}
          {parentId && !editing && (
            <div style={{ marginBottom: '1rem', padding: '0.625rem 0.875rem', backgroundColor: 'var(--info-bg)', border: '1px solid var(--info)', borderRadius: '0.5rem', fontSize: '0.8rem', color: 'var(--info)', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
              This will be created as a subdirectory
            </div>
          )}

          <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1.25rem' }}>
            <button type="button" onClick={onClose} disabled={loading} style={{ flex: 1, padding: '0.625rem', backgroundColor: 'var(--bg)', color: 'var(--text-secondary)', border: '1px solid var(--border-soft)', borderRadius: '0.5rem', fontSize: '0.875rem', fontWeight: 500, cursor: 'pointer', fontFamily: 'inherit' }}>
              Cancel
            </button>
            <button type="submit" disabled={loading} style={{ flex: 1, padding: '0.625rem', backgroundColor: 'var(--text)', color: 'var(--surface)', border: 'none', borderRadius: '0.5rem', fontSize: '0.875rem', fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}>
              {loading
                ? <><span style={{ width: '14px', height: '14px', border: '2px solid rgba(255,255,255,0.3)', borderTopColor: 'var(--surface)', borderRadius: '50%', animation: 'spin 0.7s linear infinite', display: 'inline-block' }} />Saving…</>
                : editing ? 'Save changes' : 'Create'}
            </button>
          </div>
        </form>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    </div>
  )
}
