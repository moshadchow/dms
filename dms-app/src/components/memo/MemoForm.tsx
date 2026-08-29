import { useState, useEffect } from 'react'
import { toast } from 'react-hot-toast'
import { categoriesApi } from '@/api/categories.api'
import type { Category } from '@/types/category.types'
import type { UserLevel, User } from '@/types/user.types'
import type { Document } from '@/types/document.types'
import type { MemoCreate, MemoUpdate } from '@/types/memo.types'
import Button from '@/components/ui/Button'
import AttachmentUploader from './AttachmentUploader'
import MemoRichTextEditor from './editor/MemoRichTextEditor'

interface MemoFormProps {
  initialData?: Partial<MemoCreate> | Partial<MemoUpdate>
  directories: { id: number; name: string; category_id: number }[]
  userLevels: UserLevel[]
  onSubmit: (data: MemoCreate | MemoUpdate) => void
  onCancel: () => void
  submitting?: boolean
  isEdit?: boolean
  existingAttachments?: Document[]
  error?: string
  onClearError?: () => void
  currentUser?: User | null
}

export default function MemoForm({
  initialData = {},
  directories,
  userLevels,
  onSubmit,
  onCancel,
  submitting = false,
  isEdit = false,
  existingAttachments = [],
  error,
  onClearError,
  currentUser,
}: MemoFormProps) {
  const [memo_date, setMemoDate] = useState(
    initialData.memo_date ? initialData.memo_date.split('T')[0] : new Date().toISOString().split('T')[0]
  )
  const [subject, setSubject] = useState(initialData.subject || '')
  const [body, setBody] = useState(initialData.body || '')
  const [directory_id, setDirectoryId] = useState<number | ''>(initialData.directory_id || '')
  const [user_level_ids, setUserLevelIds] = useState<number[]>(initialData.user_level_ids || [])
  const [attachmentDocs, setAttachmentDocs] = useState<Document[]>(existingAttachments)
  const [categories, setCategories] = useState<Category[]>([])
  const [categoryId, setCategoryId] = useState<number | ''>('')

  useEffect(() => {
    categoriesApi.list(true).then(setCategories).catch(() => toast.error('Failed to load categories'))
  }, [])

  useEffect(() => {
    if (initialData.subject !== undefined) setSubject(initialData.subject || '')
    if (initialData.body !== undefined) setBody(initialData.body || '')
    if (initialData.directory_id !== undefined) setDirectoryId(initialData.directory_id || '')
    if (initialData.user_level_ids !== undefined) setUserLevelIds(initialData.user_level_ids || [])
    if (initialData.memo_date !== undefined) {
      setMemoDate(initialData.memo_date ? initialData.memo_date.split('T')[0] : new Date().toISOString().split('T')[0])
    }
  }, [initialData])

  useEffect(() => {
    if (initialData.directory_id && directories.length > 0) {
      const dir = directories.find(d => d.id === initialData.directory_id)
      if (dir) setCategoryId(dir.category_id)
    }
  }, [initialData.directory_id, directories])

  const handleCategoryChange = (value: string) => {
    const id = Number(value) || ''
    setCategoryId(id)
    if (id) {
      const dirs = directories.filter((d) => d.category_id === id)
      if (dirs.length > 0) setDirectoryId(dirs[0].id)
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onClearError?.()
    if (!directory_id || !subject.trim()) {
      toast.error('Directory and subject are required')
      return
    }
    const data = {
      directory_id,
      ...(isEdit && { user_level_ids }),
      memo_date: memo_date ? new Date(memo_date).toISOString() : undefined,
      subject,
      body,
      attachment_document_ids: attachmentDocs.map((d) => ('document_id' in d ? d.document_id : d.id)),
    }
    onSubmit(data as MemoCreate | MemoUpdate)
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {error && (
        <div style={{ padding: '0.75rem 1rem', backgroundColor: 'var(--danger-bg, #fef2f2)', border: '1px solid var(--danger, #fecaca)', borderRadius: '0.5rem', color: 'var(--danger, #dc2626)', fontSize: '0.85rem' }}>
          {error}
        </div>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
        <div>
          <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 500, marginBottom: '4px', color: '#334155' }}>Category</label>
          <select
            value={categoryId}
            onChange={(e) => handleCategoryChange(e.target.value)}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid #cbd5e1', borderRadius: 6, fontSize: '0.85rem' }}
          >
            <option value="">Select category</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 500, marginBottom: '4px', color: '#334155' }}>Directory</label>
          <select
            value={directory_id}
            onChange={(e) => setDirectoryId(Number(e.target.value) || '')}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid #cbd5e1', borderRadius: 6, fontSize: '0.85rem' }}
            disabled={!categoryId}
          >
            <option value="">Select category first</option>
            {directories
              .filter((d) => !categoryId || d.category_id === categoryId)
              .map((d) => (
                <option key={d.id} value={d.id}>{d.name}</option>
              ))}
          </select>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
        <div>
          <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 500, marginBottom: '4px', color: '#334155' }}>Date</label>
          <input
            type="date"
            value={memo_date}
            onChange={(e) => setMemoDate(e.target.value)}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid #cbd5e1', borderRadius: 6, fontSize: '0.85rem' }}
          />
        </div>
        <div>
          <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 500, marginBottom: '4px', color: '#334155' }}>Subject *</label>
          <input
            type="text"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="Memo subject"
            style={{ width: '100%', padding: '8px 12px', border: '1px solid #cbd5e1', borderRadius: 6, fontSize: '0.85rem' }}
            required
          />
        </div>
      </div>

      <div>
        <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 500, marginBottom: '4px', color: '#334155' }}>Body</label>
        <MemoRichTextEditor
          value={body}
          onChange={setBody}
          placeholder="Write your memo here..."
        />
      </div>

      <div>
        <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 500, marginBottom: '4px', color: '#334155' }}>User Levels (Visibility)</label>
        {isEdit ? (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {userLevels.map((ul) => (
              <label
                key={ul.id}
                style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', cursor: 'pointer' }}
              >
                <input
                  type="checkbox"
                  checked={user_level_ids.includes(ul.id)}
                  onChange={(e) => setUserLevelIds((prev) =>
                    e.target.checked ? [...prev, ul.id] : prev.filter((id) => id !== ul.id)
                  )}
                />
                <span>{ul.name}</span>
              </label>
            ))}
          </div>
        ) : (
          <div style={{ padding: '8px 12px', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 6, fontSize: '0.85rem', color: '#334155' }}>
            {currentUser?.user_level?.name || 'All Levels (Admin)'}
          </div>
        )}
      </div>

      <AttachmentUploader
        initialAttachments={attachmentDocs}
        onChange={setAttachmentDocs}
        disabled={isEdit && existingAttachments.length > 0 && attachmentDocs.length === existingAttachments.length}
        directoryId={directory_id || undefined}
        userLevelIds={isEdit ? user_level_ids : undefined}
      />

      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '0.5rem' }}>
        <Button type="button" variant="secondary" onClick={onCancel} disabled={submitting}>
          Cancel
        </Button>
        <Button type="submit" disabled={submitting}>
          {submitting ? 'Saving...' : isEdit ? 'Save Changes' : 'Create Memo'}
        </Button>
      </div>
    </form>
  )
}