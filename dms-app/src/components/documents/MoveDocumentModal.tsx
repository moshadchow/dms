import { useState, useEffect } from 'react'
import { toast } from 'react-hot-toast'
import { documentsApi } from '@/api/documents.api'
import { categoriesApi } from '@/api/categories.api'
import { getErrorMessage } from '@/api/client'
import MoveDestinationPicker from '../directories/MoveDestinationPicker'
import type { Document } from '@/types/document.types'
import type { Category } from '@/types/category.types'

interface Props {
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
  document: Document | null
}

export default function MoveDocumentModal({ isOpen, onClose, onSuccess, document }: Props) {
  const [loading, setLoading] = useState(false)
  const [categories, setCategories] = useState<Category[]>([])

  useEffect(() => {
    if (!isOpen) return
    let cancelled = false
    categoriesApi.list()
      .then((data) => { if (!cancelled) setCategories(data) })
      .catch(() => {})
    return () => { cancelled = true }
  }, [isOpen])

  const handleDestinationSelect = async (newDirectoryId: number | null) => {
    if (!document || newDirectoryId === null) return
    setLoading(true)
    try {
      await documentsApi.move(document.id, { new_directory_id: newDirectoryId })
      toast.success('Document moved')
      onSuccess()
      onClose()
    } catch (err) {
      toast.error(getErrorMessage(err), { duration: 6000 })
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen || !document) return null

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem' }}>
      <div style={{ position: 'absolute', inset: 0, backgroundColor: 'rgba(15,23,42,0.45)', backdropFilter: 'blur(2px)' }} onClick={onClose} />
      <div style={{ position: 'relative', width: '100%', maxWidth: '480px', backgroundColor: 'var(--surface)', borderRadius: '1rem', boxShadow: '0 20px 60px rgba(0,0,0,0.15)', border: '1px solid var(--border)', overflow: 'hidden', maxHeight: '90vh', display: 'flex', flexDirection: 'column' }}>

        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '1.1rem 1.25rem', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ width: '32px', height: '32px', backgroundColor: 'var(--primary-soft)', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#4f46e5" strokeWidth="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
              </svg>
            </div>
            <h2 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text)', margin: 0 }}>Move document</h2>
          </div>
          <button onClick={onClose} disabled={loading} style={{ width: '32px', height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '8px', border: 'none', backgroundColor: 'transparent', cursor: 'pointer', color: 'var(--text-tertiary)' }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '1.25rem' }}>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', margin: '0 0 0.5rem' }}>
            Moving <strong style={{ color: 'var(--text)' }}>{document.title}</strong>
          </p>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', margin: '0 0 1rem' }}>
            Select a destination directory. Cross-category moves within the same company are allowed.
          </p>
          <MoveDestinationPicker
            currentDocumentDirectoryId={document.directory_id}
            categories={categories}
            onSelect={handleDestinationSelect}
            loading={loading}
            onClose={onClose}
          />
        </div>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    </div>
  )
}