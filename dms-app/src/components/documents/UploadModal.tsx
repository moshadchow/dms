import { useState, useRef, useCallback } from 'react'
import { toast } from 'react-hot-toast'
import { documentsApi } from '@/api/documents.api'
import { getErrorMessage } from '@/api/client'
import { formatFileSize } from '@/utils/formatters'

const ALLOWED_MIME = [
  'application/pdf',
  'application/vnd.ms-excel',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'image/jpeg',
  'image/png',
]
const ALLOWED_EXT  = '.pdf,.xlsx,.xls,.jpg,.jpeg,.png'
const MAX_BYTES    = 50 * 1024 * 1024   // 50 MB

interface Props {
  isOpen:      boolean
  onClose:     () => void
  directoryId: number
  onSuccess:   () => void
}

interface FileEntry {
  file:    File
  title:   string
  error?:  string
  done?:   boolean
}

export default function UploadModal({ isOpen, onClose, directoryId, onSuccess }: Props) {
  const inputRef                      = useRef<HTMLInputElement>(null)
  const [files, setFiles]             = useState<FileEntry[]>([])
  const [dragging, setDragging]       = useState(false)
  const [uploading, setUploading]     = useState(false)
  const [description, setDescription] = useState('')

  const addFiles = (raw: FileList | null) => {
    if (!raw) return
    const entries: FileEntry[] = []
    for (const f of Array.from(raw)) {
      if (!ALLOWED_MIME.includes(f.type)) {
        entries.push({ file: f, title: f.name.replace(/\.[^.]+$/, ''), error: 'Unsupported file type' })
      } else if (f.size > MAX_BYTES) {
        entries.push({ file: f, title: f.name.replace(/\.[^.]+$/, ''), error: 'File exceeds 50 MB limit' })
      } else {
        entries.push({ file: f, title: f.name.replace(/\.[^.]+$/, '') })
      }
    }
    setFiles((prev) => [...prev, ...entries])
  }

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    addFiles(e.dataTransfer.files)
  }, [])

  const removeFile = (idx: number) =>
    setFiles((prev) => prev.filter((_, i) => i !== idx))

  const updateTitle = (idx: number, title: string) =>
    setFiles((prev) => prev.map((f, i) => i === idx ? { ...f, title } : f))

  const handleUpload = async () => {
    const valid = files.filter((f) => !f.error && !f.done)
    if (!valid.length) return
    setUploading(true)
    let successCount = 0

    for (let i = 0; i < files.length; i++) {
      const entry = files[i]
      if (entry.error || entry.done) continue
      try {
        await documentsApi.upload(entry.file, entry.title.trim() || entry.file.name, directoryId, description.trim() || undefined)
        setFiles((prev) => prev.map((f, idx) => idx === i ? { ...f, done: true } : f))
        successCount++
      } catch (err) {
        setFiles((prev) => prev.map((f, idx) => idx === i ? { ...f, error: getErrorMessage(err) } : f))
      }
    }

    setUploading(false)
    if (successCount > 0) {
      toast.success(`${successCount} file${successCount > 1 ? 's' : ''} uploaded`)
      onSuccess()
    }
    if (files.every((f) => f.done || f.error)) handleClose()
  }

  const handleClose = () => {
    if (uploading) return
    setFiles([])
    setDescription('')
    onClose()
  }

  if (!isOpen) return null

  const pendingCount = files.filter((f) => !f.error && !f.done).length

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem' }}>
      <div style={{ position: 'absolute', inset: 0, backgroundColor: 'rgba(15,23,42,0.45)', backdropFilter: 'blur(2px)' }} onClick={handleClose} />

      <div style={{ position: 'relative', width: '100%', maxWidth: '520px', backgroundColor: 'var(--surface)', borderRadius: '1rem', boxShadow: '0 20px 60px rgba(0,0,0,0.15)', border: '1px solid var(--border)', overflow: 'hidden', maxHeight: '90vh', display: 'flex', flexDirection: 'column' }}>

        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '1.1rem 1.25rem', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ width: '32px', height: '32px', backgroundColor: 'var(--primary-soft)', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#4f46e5" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
            </div>
            <h2 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text)', margin: 0 }}>Upload documents</h2>
          </div>
          <button onClick={handleClose} disabled={uploading} style={{ width: '32px', height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '8px', border: 'none', backgroundColor: 'transparent', cursor: 'pointer', color: 'var(--text-tertiary)' }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '1.25rem' }}>

          {/* Drop zone */}
          <div
            onDrop={onDrop}
            onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onClick={() => inputRef.current?.click()}
            style={{
              border: `2px dashed ${dragging ? '#4f46e5' : 'var(--surface-3)'}`,
              borderRadius: '0.75rem',
              padding: '2rem',
              textAlign: 'center',
              cursor: 'pointer',
              backgroundColor: dragging ? '#eef2ff' : 'var(--bg)',
              transition: 'all 150ms',
              marginBottom: files.length ? '1rem' : 0,
            }}
          >
            <div style={{ width: '40px', height: '40px', backgroundColor: 'var(--primary-soft)', borderRadius: '10px', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 0.75rem' }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#4f46e5" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
            </div>
            <p style={{ fontWeight: 600, color: 'var(--text-secondary)', margin: '0 0 4px', fontSize: '0.9rem' }}>
              Drop files here or <span style={{ color: '#4f46e5' }}>browse</span>
            </p>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)', margin: 0 }}>
              PDF, Excel, JPG, PNG — max 50 MB each
            </p>
            <input ref={inputRef} type="file" accept={ALLOWED_EXT} multiple style={{ display: 'none' }} onChange={(e) => addFiles(e.target.files)} />
          </div>

          {/* File list */}
          {files.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '1rem' }}>
              {files.map((entry, idx) => (
                <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '8px 10px', borderRadius: '8px', border: `1px solid ${entry.error ? '#fecaca' : entry.done ? '#bbf7d0' : 'var(--surface-2)'}`, backgroundColor: entry.error ? '#fef2f2' : entry.done ? '#f0fdf4' : 'var(--bg)' }}>
                  <div style={{ flexShrink: 0, color: entry.error ? '#dc2626' : entry.done ? '#16a34a' : '#4f46e5' }}>
                    {entry.done
                      ? <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                      : entry.error
                        ? <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                        : <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                    }
                  </div>
                  <div style={{ flex: 1, overflow: 'hidden' }}>
                    {!entry.done && !entry.error ? (
                      <input
                        value={entry.title}
                        onChange={(e) => updateTitle(idx, e.target.value)}
                        placeholder="Document title"
                        style={{ width: '100%', border: 'none', background: 'transparent', fontSize: '0.82rem', fontWeight: 500, color: 'var(--text-secondary)', outline: 'none', fontFamily: 'inherit' }}
                      />
                    ) : (
                      <p style={{ fontSize: '0.82rem', fontWeight: 500, color: entry.error ? '#dc2626' : '#16a34a', margin: 0 }}>
                        {entry.error ?? entry.title}
                      </p>
                    )}
                    <p style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', margin: '1px 0 0' }}>
                      {entry.file.name} · {formatFileSize(entry.file.size)}
                    </p>
                  </div>
                  {!entry.done && (
                    <button onClick={() => removeFile(idx)} style={{ border: 'none', background: 'none', cursor: 'pointer', color: 'var(--text-tertiary)', padding: '2px', flexShrink: 0 }}>
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Description field */}
          {files.length > 0 && (
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
                Description <span style={{ fontWeight: 400, color: 'var(--text-tertiary)' }}>(optional, applies to all)</span>
              </label>
              <textarea
                className="input"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Brief description of these documents..."
                rows={2}
                style={{ resize: 'none', fontFamily: 'inherit' }}
              />
            </div>
          )}
        </div>

        {/* Footer */}
        {files.length > 0 && (
          <div style={{ borderTop: '1px solid var(--border)', padding: '1rem 1.25rem', display: 'flex', gap: '0.75rem', flexShrink: 0 }}>
            <button onClick={handleClose} disabled={uploading} style={{ flex: 1, padding: '0.625rem', backgroundColor: 'var(--bg)', color: 'var(--text-secondary)', border: '1px solid var(--border-soft)', borderRadius: '0.5rem', fontSize: '0.875rem', fontWeight: 500, cursor: 'pointer', fontFamily: 'inherit' }}>
              Cancel
            </button>
            <button
              onClick={handleUpload}
              disabled={uploading || pendingCount === 0}
              style={{ flex: 2, padding: '0.625rem', backgroundColor: pendingCount === 0 ? 'var(--text-tertiary)' : 'var(--text)', color: 'var(--surface)', border: 'none', borderRadius: '0.5rem', fontSize: '0.875rem', fontWeight: 600, cursor: pendingCount === 0 ? 'not-allowed' : 'pointer', fontFamily: 'inherit', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
            >
              {uploading
                ? <><span style={{ width: '14px', height: '14px', border: '2px solid rgba(255,255,255,0.3)', borderTopColor: 'var(--surface)', borderRadius: '50%', animation: 'spin 0.7s linear infinite', display: 'inline-block' }} />Uploading…</>
                : `Upload ${pendingCount} file${pendingCount !== 1 ? 's' : ''}`
              }
            </button>
          </div>
        )}
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    </div>
  )
}
