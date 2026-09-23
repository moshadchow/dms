import { useState, useRef } from 'react'
import Modal from '@/components/ui/Modal'
import Button from '@/components/ui/Button'
import { correspondenceApi } from '@/api/correspondence.api'
import { getErrorMessage } from '@/api/client'
import toast from 'react-hot-toast'
import type { CorrespondenceDetail } from '@/types/correspondence.types'

interface Props {
  isOpen: boolean
  parent: CorrespondenceDetail
  onClose: () => void
  onSuccess: (reply: CorrespondenceDetail) => void
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '8px 10px', borderRadius: '6px',
  border: '1px solid var(--border)', backgroundColor: 'var(--surface)',
  color: 'var(--text)', fontSize: '0.85rem', outline: 'none', boxSizing: 'border-box',
}

const ALLOWED_MIME = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.ms-excel',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'image/jpeg',
  'image/png',
]

export default function CorrespondenceReplyDialog({ isOpen, parent, onClose, onSuccess }: Props) {
  const [subject, setSubject] = useState(`Re: ${parent.subject}`)
  const [body, setBody] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (!f) return
    if (!ALLOWED_MIME.includes(f.type)) {
      toast.error('File type not supported. Use PDF, DOCX, Excel, or images.')
      return
    }
    if (f.size > 50 * 1024 * 1024) {
      toast.error('File size exceeds 50 MB limit')
      return
    }
    setFile(f)
  }

  const handleConfirm = async () => {
    if (!subject.trim()) {
      toast.error('Subject is required')
      return
    }
    if (!body.trim()) {
      toast.error('Body is required for a reply')
      return
    }
    setLoading(true)
    try {
      const reply = await correspondenceApi.createReply(parent.id, {
        direction: 'outbound',
        subject: subject.trim(),
        body,
        priority: parent.priority,
        category_id: parent.category_id,
        user_level_ids: parent.user_level_ids,
      })
      if (file) {
        try {
          await correspondenceApi.addAttachment(reply.id, file, 'supporting')
        } catch (uploadErr) {
          toast.error(`Reply created but file upload failed: ${getErrorMessage(uploadErr)}`)
        }
      }
      toast.success('Reply created')
      onSuccess(reply)
      onClose()
      setBody('')
      setFile(null)
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Compose Reply"
      subtitle={`Replying to ${parent.reference_number} — ${parent.subject}`}
      footer={
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={handleConfirm} loading={loading}>Create Reply</Button>
        </div>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <div>
          <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>Subject *</label>
          <input value={subject} onChange={(e) => setSubject(e.target.value)} style={inputStyle} />
        </div>
        <div>
          <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>Body *</label>
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={8}
            placeholder="Write your reply here..."
            style={{ ...inputStyle, resize: 'vertical', fontFamily: 'inherit' }}
          />
        </div>
        <div
          style={{
            border: '2px dashed #cbd5e1', borderRadius: 8, padding: '1rem', textAlign: 'center',
            cursor: 'pointer', fontSize: '0.82rem', color: '#334155',
          }}
          onClick={() => fileInputRef.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => { e.preventDefault(); setFile(e.dataTransfer.files?.[0] ?? null) }}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.xlsx,.xls,.jpg,.jpeg,.png"
            style={{ display: 'none' }}
            onChange={handleFileSelect}
          />
          {file ? (
            <strong>{file.name} ({(file.size / 1024).toFixed(1)} KB)</strong>
          ) : (
            <>
              Drag & drop or click to attach supporting documents
              <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '4px' }}>PDF, DOCX, Excel, Images (max 50 MB)</div>
            </>
          )}
        </div>
      </div>
    </Modal>
  )
}