import { useState, useEffect } from 'react'
import { toast } from 'react-hot-toast'
import { documentsApi } from '@/api/documents.api'
import { getErrorMessage } from '@/api/client'
import type { Document } from '@/types/document.types'

interface Props {
  isOpen:    boolean
  doc:       Document | null
  onClose:   () => void
  onSuccess: () => void
}

export default function EditDocumentModal({ isOpen, doc, onClose, onSuccess }: Props) {
  const [title, setTitle]         = useState('')
  const [description, setDesc]    = useState('')
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState('')

  useEffect(() => {
    if (doc) {
      setTitle(doc.title)
      setDesc(doc.description ?? '')
    }
    setError('')
  }, [doc, isOpen])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim()) { setError('Title is required.'); return }
    if (!doc) return

    setLoading(true)
    setError('')
    try {
      await documentsApi.update(doc.id, {
        title: title.trim(),
        description: description.trim() || undefined,
      })
      toast.success('Document updated')
      onSuccess()
      onClose()
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen || !doc) return null

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem' }}>
      <div style={{ position: 'absolute', inset: 0, backgroundColor: 'rgba(15,23,42,0.45)', backdropFilter: 'blur(2px)' }} onClick={onClose} />
      <div style={{ position: 'relative', width: '100%', maxWidth: '420px', backgroundColor: 'var(--surface)', borderRadius: '1rem', boxShadow: '0 20px 60px rgba(0,0,0,0.15)', border: '1px solid var(--border)' }}>

        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '1.1rem 1.25rem', borderBottom: '1px solid var(--border)' }}>
          <h2 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text)', margin: 0 }}>Edit document</h2>
          <button onClick={onClose} style={{ width: '32px', height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '8px', border: 'none', backgroundColor: 'transparent', cursor: 'pointer', color: 'var(--text-tertiary)' }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>

        <form onSubmit={handleSubmit} style={{ padding: '1.25rem' }}>
          {error && (
            <div style={{ marginBottom: '1rem', padding: '0.75rem', backgroundColor: 'var(--danger-bg)', border: '1px solid var(--danger)', borderRadius: '0.5rem', color: 'var(--danger)', fontSize: '0.85rem' }}>
              {error}
            </div>
          )}

          <div style={{ marginBottom: '1rem' }}>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
              Title <span style={{ color: '#ef4444' }}>*</span>
            </label>
            <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} disabled={loading} autoFocus />
          </div>

          <div style={{ marginBottom: '1rem' }}>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>Description</label>
            <textarea className="input" value={description} onChange={(e) => setDesc(e.target.value)} rows={3} disabled={loading} style={{ resize: 'vertical', fontFamily: 'inherit' }} />
          </div>

          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <button type="button" onClick={onClose} disabled={loading} style={{ flex: 1, padding: '0.625rem', backgroundColor: 'var(--bg)', color: 'var(--text-secondary)', border: '1px solid var(--border-soft)', borderRadius: '0.5rem', fontSize: '0.875rem', fontWeight: 500, cursor: 'pointer', fontFamily: 'inherit' }}>
              Cancel
            </button>
            <button type="submit" disabled={loading} style={{ flex: 1, padding: '0.625rem', backgroundColor: 'var(--text)', color: 'var(--surface)', border: 'none', borderRadius: '0.5rem', fontSize: '0.875rem', fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}>
              {loading ? <><span style={{ width: '14px', height: '14px', border: '2px solid rgba(255,255,255,0.3)', borderTopColor: 'var(--surface)', borderRadius: '50%', animation: 'spin 0.7s linear infinite', display: 'inline-block' }} />Saving…</> : 'Save changes'}
            </button>
          </div>
        </form>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    </div>
  )
}
