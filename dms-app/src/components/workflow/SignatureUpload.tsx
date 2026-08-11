import { useRef, useState } from 'react'
import Button from '@/components/ui/Button'

interface SignatureUploadProps {
  onFileSelected: (file: File) => void
  onCancel?: () => void
  accept?: string
}

const dropStyle: React.CSSProperties = {
  border: '2px dashed #cbd5e1',
  borderRadius: '8px',
  padding: '2rem',
  textAlign: 'center',
  cursor: 'pointer',
  transition: 'border-color 150ms',
}

const previewStyle: React.CSSProperties = {
  maxWidth: '300px',
  maxHeight: '150px',
  objectFit: 'contain',
  borderRadius: '6px',
  border: '1px solid #e2e8f0',
}

const actionsStyle: React.CSSProperties = {
  display: 'flex',
  gap: '8px',
  marginTop: '8px',
}

export default function SignatureUpload({
  onFileSelected,
  onCancel,
  accept = 'image/png,image/jpeg,image/svg+xml',
}: SignatureUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)

  const handleFile = (file: File) => {
    if (!file.type.startsWith('image/')) return
    const url = URL.createObjectURL(file)
    setPreview(url)
    onFileSelected(file)
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  return (
    <div>
      <div
        style={{ ...dropStyle, borderColor: dragOver ? '#4f46e5' : '#cbd5e1' }}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          onChange={handleChange}
          style={{ display: 'none' }}
        />
        {preview ? (
          <div>
            <img src={preview} alt="Signature preview" style={previewStyle} />
            <p style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.5rem' }}>
              Click or drop to replace
            </p>
          </div>
        ) : (
          <div>
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="1.5" style={{ margin: '0 auto 0.5rem' }}>
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
              <circle cx="8.5" cy="8.5" r="1.5" />
              <polyline points="21 15 16 10 5 21" />
            </svg>
            <p style={{ fontSize: '0.85rem', color: '#64748b', margin: 0 }}>
              Drag & drop a signature image, or click to browse
            </p>
            <p style={{ fontSize: '0.72rem', color: '#94a3b8', margin: '4px 0 0' }}>
              PNG, JPG, or SVG
            </p>
          </div>
        )}
      </div>
      <div style={actionsStyle}>
        {preview && (
          <Button variant="secondary" size="sm" onClick={() => { setPreview(null); inputRef.current?.click() }}>
            Replace
          </Button>
        )}
        {onCancel && (
          <Button variant="ghost" size="sm" onClick={onCancel}>
            Cancel
          </Button>
        )}
      </div>
    </div>
  )
}
