import { useState, useEffect, useRef } from 'react'
import Button from '@/components/ui/Button'
import { categoriesApi } from '@/api/categories.api'
import { correspondenceApi } from '@/api/correspondence.api'
import type { Category } from '@/types/document.types'
import type {
  CorrespondenceCreate,
  CorrespondenceDirection,
  CorrespondenceDetail,
  CorrespondencePriority,
} from '@/types/correspondence.types'
import toast from 'react-hot-toast'

interface Props {
  initialDirection?: CorrespondenceDirection
  parent?: CorrespondenceDetail | null
  onSubmit: (data: CorrespondenceCreate, file?: File | null) => Promise<void>
  onCancel: () => void
  loading?: boolean
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '8px 10px', borderRadius: '6px',
  border: '1px solid var(--border)', backgroundColor: 'var(--surface)',
  color: 'var(--text)', fontSize: '0.85rem', outline: 'none', boxSizing: 'border-box',
}

const labelStyle: React.CSSProperties = {
  display: 'block', fontSize: '0.78rem', fontWeight: 600,
  color: 'var(--text-secondary)', marginBottom: '4px',
}

const ALLOWED_MIME = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.ms-excel',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'image/jpeg',
  'image/png',
]

export default function CorrespondenceForm({ initialDirection, parent, onSubmit, onCancel, loading }: Props) {
  const isReply = !!parent
  const [direction, setDirection] = useState<CorrespondenceDirection>(isReply ? 'outbound' : (initialDirection ?? 'outbound'))
  const [subject, setSubject] = useState<string>(isReply ? `Re: ${parent!.subject}` : '')
  const [body, setBody] = useState('')
  const [priority, setPriority] = useState<CorrespondencePriority>('normal')
  const [categoryId, setCategoryId] = useState<number | null>(parent?.category_id ?? null)
  const [senderName, setSenderName] = useState('')
  const [senderOrg, setSenderOrg] = useState('')
  const [senderEmail, setSenderEmail] = useState('')
  const [senderPhone, setSenderPhone] = useState('')
  const [recipientName, setRecipientName] = useState('')
  const [recipientOrg, setRecipientOrg] = useState('')
  const [recipientEmail, setRecipientEmail] = useState('')
  const [recipientPhone, setRecipientPhone] = useState('')
  const [dateReceived, setDateReceived] = useState('')
  const [responseRequired, setResponseRequired] = useState(false)
  const [responseDeadline, setResponseDeadline] = useState('')
  const [nextRef, setNextRef] = useState('')
  const [categories, setCategories] = useState<Category[]>([])
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    categoriesApi.list().then(res => setCategories(res.items ?? res)).catch(() => {})
    correspondenceApi.getNextReference().then(res => setNextRef(res.reference)).catch(() => {})
  }, [])

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (!ALLOWED_MIME.includes(file.type)) {
      toast.error('File type not supported. Use PDF, DOCX, Excel, or images.')
      return
    }
    if (file.size > 50 * 1024 * 1024) {
      toast.error('File size exceeds 50 MB limit')
      return
    }
    setSelectedFile(file)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    const file = e.dataTransfer.files?.[0]
    if (!file) return
    if (!ALLOWED_MIME.includes(file.type)) {
      toast.error('File type not supported. Use PDF, DOCX, Excel, or images.')
      return
    }
    setSelectedFile(file)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!subject.trim()) { toast.error('Subject is required'); return }
    if ((direction === 'outbound' || direction === 'internal') && !body.trim()) {
      toast.error('Body is required for outbound/internal correspondence'); return
    }
    if ((direction === 'outbound' || direction === 'internal') && !categoryId) {
      toast.error('Category is required for outbound/internal correspondence'); return
    }
    if (direction === 'inbound' && !dateReceived) {
      toast.error('Date received is required for inbound correspondence'); return
    }

    const data: CorrespondenceCreate = {
      direction,
      subject: subject.trim(),
      body: body || undefined,
      priority,
      category_id: categoryId,
      sender_name: senderName || undefined,
      sender_organization: senderOrg || undefined,
      sender_email: senderEmail || undefined,
      sender_phone: senderPhone || undefined,
      recipient_name: recipientName || undefined,
      recipient_organization: recipientOrg || undefined,
      recipient_email: recipientEmail || undefined,
      recipient_phone: recipientPhone || undefined,
      date_received: dateReceived ? new Date(dateReceived).toISOString() : undefined,
      response_required: responseRequired,
      response_deadline: responseDeadline ? new Date(responseDeadline).toISOString() : undefined,
    }
    await onSubmit(data, selectedFile)
  }

  return (
    <form onSubmit={handleSubmit}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Reference preview */}
        {nextRef && (
          <div style={{ padding: '8px 12px', backgroundColor: 'var(--surface-2)', borderRadius: '6px', fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
            Reference: <strong style={{ color: 'var(--primary)' }}>{nextRef}</strong>
          </div>
        )}

        {/* Reply context banner */}
        {parent && (
          <div style={{ padding: '8px 12px', backgroundColor: 'var(--primary-soft, #eef2ff)', borderRadius: '6px', fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
            Replying to <strong style={{ color: 'var(--primary)' }}>{parent.reference_number}</strong> — {parent.subject}
          </div>
        )}

        {/* Direction (only if not pre-set) */}
        {!initialDirection && !parent && (
          <div>
            <label style={labelStyle}>Direction *</label>
            <div style={{ display: 'flex', gap: '8px' }}>
              {(['inbound', 'outbound', 'internal'] as const).map(d => (
                <button
                  key={d}
                  type="button"
                  onClick={() => setDirection(d)}
                  style={{
                    padding: '8px 16px', borderRadius: '6px', border: '1.5px solid',
                    borderColor: direction === d ? 'var(--primary)' : 'var(--border)',
                    backgroundColor: direction === d ? 'var(--primary-soft)' : 'var(--surface)',
                    color: direction === d ? 'var(--primary)' : 'var(--text-secondary)',
                    fontWeight: 600, fontSize: '0.82rem', cursor: 'pointer',
                  }}
                >
                  {d === 'inbound' ? 'Incoming' : d === 'outbound' ? 'Outgoing' : 'Internal'}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Subject */}
        <div>
          <label style={labelStyle}>Subject *</label>
          <input value={subject} onChange={(e) => setSubject(e.target.value)} style={inputStyle} />
        </div>

        {/* Sender / Recipient */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
          {direction !== 'outbound' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <h4 style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text)' }}>Sender</h4>
              <input placeholder="Name" value={senderName} onChange={(e) => setSenderName(e.target.value)} style={inputStyle} />
              <input placeholder="Organization" value={senderOrg} onChange={(e) => setSenderOrg(e.target.value)} style={inputStyle} />
              <input placeholder="Email" value={senderEmail} onChange={(e) => setSenderEmail(e.target.value)} style={inputStyle} />
              <input placeholder="Phone" value={senderPhone} onChange={(e) => setSenderPhone(e.target.value)} style={inputStyle} />
            </div>
          )}
          {direction !== 'inbound' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <h4 style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text)' }}>Recipient</h4>
              <input placeholder="Name" value={recipientName} onChange={(e) => setRecipientName(e.target.value)} style={inputStyle} />
              <input placeholder="Organization" value={recipientOrg} onChange={(e) => setRecipientOrg(e.target.value)} style={inputStyle} />
              <input placeholder="Email" value={recipientEmail} onChange={(e) => setRecipientEmail(e.target.value)} style={inputStyle} />
              <input placeholder="Phone" value={recipientPhone} onChange={(e) => setRecipientPhone(e.target.value)} style={inputStyle} />
            </div>
          )}
        </div>

        {/* Priority, Category, Date */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px' }}>
          <div>
            <label style={labelStyle}>Priority</label>
            <select value={priority} onChange={(e) => setPriority(e.target.value as CorrespondencePriority)} style={inputStyle}>
              <option value="low">Low</option>
              <option value="normal">Normal</option>
              <option value="high">High</option>
              <option value="urgent">Urgent</option>
            </select>
          </div>
          <div>
            <label style={labelStyle}>Category{direction !== 'inbound' ? ' *' : ''}</label>
            <select value={categoryId ?? ''} onChange={(e) => setCategoryId(Number(e.target.value) || null)} style={inputStyle}>
              <option value="">— None —</option>
              {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          {direction === 'inbound' && (
            <div>
              <label style={labelStyle}>Date Received *</label>
              <input type="datetime-local" value={dateReceived} onChange={(e) => setDateReceived(e.target.value)} style={inputStyle} />
            </div>
          )}
        </div>

        {/* Response */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', alignItems: 'end' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <input
              type="checkbox"
              id="resp-required"
              checked={responseRequired}
              onChange={(e) => setResponseRequired(e.target.checked)}
              style={{ width: '16px', height: '16px' }}
            />
            <label htmlFor="resp-required" style={{ fontSize: '0.82rem', color: 'var(--text)' }}>Response Required</label>
          </div>
          {responseRequired && (
            <div>
              <label style={labelStyle}>Response Deadline *</label>
              <input type="datetime-local" value={responseDeadline} onChange={(e) => setResponseDeadline(e.target.value)} style={inputStyle} />
            </div>
          )}
        </div>

        {/* Body (for outbound/internal) */}
        {direction !== 'inbound' && (
          <div>
            <label style={labelStyle}>Body *</label>
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={10}
              placeholder="Write the correspondence body here..."
              style={{ ...inputStyle, resize: 'vertical', fontFamily: 'inherit' }}
            />
          </div>
        )}

        {/* File Upload */}
        <div
          style={{
            border: '2px dashed #cbd5e1',
            borderRadius: 8,
            padding: '1.25rem',
            textAlign: 'center',
            cursor: 'pointer',
            transition: 'border-color 150ms',
          }}
          onClick={() => fileInputRef.current?.click()}
          onDrop={handleDrop}
          onDragOver={(e) => e.preventDefault()}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.xlsx,.xls,.jpg,.jpeg,.png"
            style={{ display: 'none' }}
            onChange={handleFileSelect}
          />
          {selectedFile ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', textAlign: 'left' }}>
              <span style={{ fontSize: '0.85rem' }}>
                <strong>{selectedFile.name}</strong>{' '}
                <span style={{ color: '#64748b' }}>({(selectedFile.size / 1024).toFixed(1)} KB)</span>
              </span>
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); setSelectedFile(null) }}
                style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: '1rem' }}
              >
                ×
              </button>
            </div>
          ) : (
            <>
              <p style={{ margin: 0, fontSize: '0.85rem', color: '#334155' }}>
                {direction === 'inbound'
                  ? 'Drag & drop or click to upload the received document *'
                  : 'Drag & drop or click to attach supporting documents'}
              </p>
              <p style={{ margin: '4px 0 0', fontSize: '0.75rem', color: '#94a3b8' }}>PDF, DOCX, Excel, Images (max 50 MB)</p>
            </>
          )}
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', paddingTop: '8px', borderTop: '1px solid var(--border)' }}>
          <Button type="button" variant="secondary" onClick={onCancel}>Cancel</Button>
          <Button type="submit" loading={loading}>Save Draft</Button>
        </div>
      </div>
    </form>
  )
}
