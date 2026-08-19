import { useState, useRef } from 'react'
import { toast } from 'react-hot-toast'
import { documentsApi } from '@/api/documents.api'
import type { Document } from '@/types/document.types'

interface AttachmentUploaderProps {
  initialAttachments?: Document[]
  onChange: (documents: Document[]) => void
  disabled?: boolean
  directoryId?: number
  userLevelIds?: number[]
}

export default function AttachmentUploader({
  initialAttachments = [],
  onChange,
  disabled = false,
  directoryId,
  userLevelIds,
}: AttachmentUploaderProps) {
  const [attachments, setAttachments] = useState<Document[]>(initialAttachments)
  const [uploading, setUploading] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFiles = async (files: FileList) => {
    if (!files.length) return
    if (!directoryId) {
      toast.error('Select a directory before uploading attachments')
      return
    }
    setUploading(true)
    const newAttachments = [...attachments]
    for (const file of Array.from(files)) {
      try {
        const doc = await documentsApi.upload(
          file,
          file.name,
          directoryId,
          undefined,
          userLevelIds,
        )
        newAttachments.push(doc)
      } catch {
        toast.error(`Failed to upload ${file.name}`)
      }
    }
    setAttachments(newAttachments)
    onChange(newAttachments)
    setUploading(false)
    if (inputRef.current) inputRef.current.value = ''
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) handleFiles(e.target.files)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    if (e.dataTransfer.files) handleFiles(e.dataTransfer.files)
  }

  const removeAttachment = (index: number) => {
    setAttachments((prev) => prev.filter((_, i) => i !== index))
    onChange(attachments.filter((_, i) => i !== index))
  }

  if (disabled) {
    return (
      <div style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: '1rem' }}>
        <p style={{ fontSize: '0.85rem', color: '#64748b', marginBottom: '0.5rem' }}>
          Attachments (view only)
        </p>
        <ul style={{ margin: 0, paddingLeft: '1.25rem' }}>
          {attachments.map((doc, i) => (
            <li key={i} style={{ fontSize: '0.85rem', margin: '4px 0' }}>
              {doc.file_name} ({doc.file_type}, {(doc.file_size / 1024).toFixed(1)} KB)
            </li>
          ))}
        </ul>
      </div>
    )
  }

  return (
    <div
      style={{
        border: '2px dashed #cbd5e1',
        borderRadius: 8,
        padding: '1.5rem',
        textAlign: 'center',
        cursor: 'pointer',
        transition: 'border-color 150ms',
      }}
      onClick={() => inputRef.current?.click()}
      onDrop={handleDrop}
      onDragOver={(e) => e.preventDefault()}
    >
      <input
        ref={inputRef}
        type="file"
        multiple
        style={{ display: 'none' }}
        onChange={handleChange}
        disabled={uploading}
      />

      {uploading ? (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
          <div className="spinner" style={{ width: 24, height: 24, border: '3px solid #cbd5e1', borderTopColor: '#4f46e5', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
          <p style={{ fontSize: '0.85rem', color: '#64748b' }}>Uploading...</p>
        </div>
      ) : !directoryId ? (
        <p style={{ margin: 0, fontSize: '0.85rem', color: '#94a3b8' }}>Select a directory above to attach files</p>
      ) : (
        <>
          <p style={{ margin: 0, fontSize: '0.9rem', color: '#334155' }}>Drag & drop or click to attach supporting documents</p>
          <p style={{ margin: '4px 0 0', fontSize: '0.75rem', color: '#94a3b8' }}>PDF, DOCX, Excel, Images</p>
        </>
      )}

      {attachments.length > 0 && (
        <ul style={{ margin: '1rem 0 0', paddingLeft: 0, listStyle: 'none', textAlign: 'left' }}>
          {attachments.map((doc, i) => (
            <li
              key={i}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '6px 10px',
                background: '#f8fafc',
                border: '1px solid #e2e8f0',
                borderRadius: 6,
                marginBottom: 6,
                fontSize: '0.8rem',
              }}
            >
              <span>
                <strong>{doc.file_name}</strong> {' '}
                <span style={{ color: '#64748b' }}>({doc.file_type.toUpperCase()}, {(doc.file_size / 1024).toFixed(1)} KB)</span>
              </span>
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); removeAttachment(i) }}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#ef4444',
                  cursor: 'pointer',
                  padding: 0,
                  fontSize: '1rem',
                }}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}