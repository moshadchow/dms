import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { correspondenceApi } from '@/api/correspondence.api'
import type { CorrespondenceDetail, CorrespondenceUpdate, CorrespondencePriority } from '@/types/correspondence.types'
import Button from '@/components/ui/Button'
import { getErrorMessage } from '@/api/client'
import { categoriesApi } from '@/api/categories.api'
import type { Category } from '@/types/document.types'

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

export default function CorrespondenceEditPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [corr, setCorr] = useState<CorrespondenceDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [categories, setCategories] = useState<Category[]>([])

  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [priority, setPriority] = useState<string>('normal')
  const [categoryId, setCategoryId] = useState<number | null>(null)
  const [senderName, setSenderName] = useState('')
  const [senderOrg, setSenderOrg] = useState('')
  const [senderEmail, setSenderEmail] = useState('')
  const [senderPhone, setSenderPhone] = useState('')
  const [recipientName, setRecipientName] = useState('')
  const [recipientOrg, setRecipientOrg] = useState('')
  const [recipientEmail, setRecipientEmail] = useState('')
  const [recipientPhone, setRecipientPhone] = useState('')
  const [responseRequired, setResponseRequired] = useState(false)
  const [responseDeadline, setResponseDeadline] = useState('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploadingFile, setUploadingFile] = useState(false)
  const [removingAttId, setRemovingAttId] = useState<number | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!id) return
    Promise.all([
      correspondenceApi.get(Number(id)),
      categoriesApi.list().then(res => setCategories(res.items ?? res)),
    ]).then(([data]) => {
      setCorr(data)
      setSubject(data.subject)
      setBody(data.body || '')
      setPriority(data.priority)
      setCategoryId(data.category_id)
      setSenderName(data.sender_name || '')
      setSenderOrg(data.sender_organization || '')
      setSenderEmail(data.sender_email || '')
      setSenderPhone(data.sender_phone || '')
      setRecipientName(data.recipient_name || '')
      setRecipientOrg(data.recipient_organization || '')
      setRecipientEmail(data.recipient_email || '')
      setRecipientPhone(data.recipient_phone || '')
      setResponseRequired(data.response_required)
      setResponseDeadline(data.response_deadline ? data.response_deadline.slice(0, 16) : '')
    }).catch(err => {
      toast.error(getErrorMessage(err))
      navigate('/correspondence')
    }).finally(() => setLoading(false))
  }, [id])

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
    if (file.size > 50 * 1024 * 1024) {
      toast.error('File size exceeds 50 MB limit')
      return
    }
    setSelectedFile(file)
  }

  const handleRemoveAttachment = async (attId: number) => {
    if (!corr) return
    setRemovingAttId(attId)
    try {
      await correspondenceApi.removeAttachment(corr.id, attId)
      toast.success('Attachment removed')
      const refreshed = await correspondenceApi.get(corr.id)
      setCorr(refreshed)
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setRemovingAttId(null)
    }
  }

  const handleSave = async () => {
    if (!corr) return
    if (!subject.trim()) { toast.error('Subject is required'); return }
    setSaving(true)
    try {
      const data: CorrespondenceUpdate = {
        subject: subject.trim(),
        body: body || undefined,
        priority: priority as CorrespondencePriority,
        category_id: categoryId,
        sender_name: senderName || undefined,
        sender_organization: senderOrg || undefined,
        sender_email: senderEmail || undefined,
        sender_phone: senderPhone || undefined,
        recipient_name: recipientName || undefined,
        recipient_organization: recipientOrg || undefined,
        recipient_email: recipientEmail || undefined,
        recipient_phone: recipientPhone || undefined,
        response_required: responseRequired,
        response_deadline: responseDeadline ? new Date(responseDeadline).toISOString() : undefined,
      }
      await correspondenceApi.update(corr.id, data)

      if (selectedFile) {
        setUploadingFile(true)
        try {
          const existingOriginal = corr.attachments?.find(a => a.attachment_type === 'original')
          await correspondenceApi.addAttachment(corr.id, selectedFile, 'original')
          if (existingOriginal) {
            await correspondenceApi.removeAttachment(corr.id, existingOriginal.id)
          }
        } catch (uploadErr) {
          toast.error(`Correspondence updated but file upload failed: ${getErrorMessage(uploadErr)}`)
        } finally {
          setUploadingFile(false)
        }
      }

      toast.success('Correspondence updated')
      navigate(`/correspondence/${corr.id}`)
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  if (loading || !corr) {
    return <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-tertiary)' }}>Loading...</div>
  }

  return (
    <div style={{ padding: '1.5rem', maxWidth: '900px', margin: '0 auto' }}>
      <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--text)', margin: '0 0 1.5rem' }}>
        Edit {corr.reference_number}
      </h1>
      <div style={{ backgroundColor: 'var(--surface)', borderRadius: '8px', border: '1px solid var(--border)', padding: '1.5rem' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <label style={labelStyle}>Subject *</label>
            <input value={subject} onChange={(e) => setSubject(e.target.value)} style={inputStyle} />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            {corr.direction !== 'outbound' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <h4 style={{ margin: 0, fontSize: '0.85rem' }}>Sender</h4>
                <input placeholder="Name" value={senderName} onChange={(e) => setSenderName(e.target.value)} style={inputStyle} />
                <input placeholder="Organization" value={senderOrg} onChange={(e) => setSenderOrg(e.target.value)} style={inputStyle} />
                <input placeholder="Email" value={senderEmail} onChange={(e) => setSenderEmail(e.target.value)} style={inputStyle} />
                <input placeholder="Phone" value={senderPhone} onChange={(e) => setSenderPhone(e.target.value)} style={inputStyle} />
              </div>
            )}
            {corr.direction !== 'inbound' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <h4 style={{ margin: 0, fontSize: '0.85rem' }}>Recipient</h4>
                <input placeholder="Name" value={recipientName} onChange={(e) => setRecipientName(e.target.value)} style={inputStyle} />
                <input placeholder="Organization" value={recipientOrg} onChange={(e) => setRecipientOrg(e.target.value)} style={inputStyle} />
                <input placeholder="Email" value={recipientEmail} onChange={(e) => setRecipientEmail(e.target.value)} style={inputStyle} />
                <input placeholder="Phone" value={recipientPhone} onChange={(e) => setRecipientPhone(e.target.value)} style={inputStyle} />
              </div>
            )}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px' }}>
            <div>
              <label style={labelStyle}>Priority</label>
              <select value={priority} onChange={(e) => setPriority(e.target.value)} style={inputStyle}>
                <option value="low">Low</option>
                <option value="normal">Normal</option>
                <option value="high">High</option>
                <option value="urgent">Urgent</option>
              </select>
            </div>
            <div>
              <label style={labelStyle}>Category</label>
              <select value={categoryId ?? ''} onChange={(e) => setCategoryId(Number(e.target.value) || null)} style={inputStyle}>
                <option value="">— None —</option>
                {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            <div style={{ display: 'flex', alignItems: 'end' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <input type="checkbox" id="resp" checked={responseRequired} onChange={(e) => setResponseRequired(e.target.checked)} style={{ width: '16px', height: '16px' }} />
                <label htmlFor="resp" style={{ fontSize: '0.82rem' }}>Response Required</label>
              </div>
            </div>
          </div>
          {responseRequired && (
            <div>
              <label style={labelStyle}>Response Deadline</label>
              <input type="datetime-local" value={responseDeadline} onChange={(e) => setResponseDeadline(e.target.value)} style={inputStyle} />
            </div>
          )}
          {corr.direction !== 'inbound' && (
            <div>
              <label style={labelStyle}>Body</label>
              <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={10} style={{ ...inputStyle, resize: 'vertical', fontFamily: 'inherit' }} />
            </div>
          )}
          {corr.direction === 'inbound' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {corr.attachments && corr.attachments.length > 0 && (
                <div>
                  <label style={labelStyle}>Received Document</label>
                  <ul style={{ margin: 0, paddingLeft: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {corr.attachments.map(att => (
                      <li key={att.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 10px', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 6, fontSize: '0.8rem' }}>
                        <span>
                          <strong>{att.file_name}</strong>{' '}
                          <span style={{ color: '#64748b' }}>({att.file_type?.toUpperCase()}, {att.file_size != null ? `${(att.file_size / 1024).toFixed(1)} KB` : '—'})</span>
                          <span style={{ marginLeft: 6, padding: '1px 6px', borderRadius: 4, fontSize: '0.7rem', background: att.attachment_type === 'original' ? '#dbeafe' : '#f1f5f9', color: att.attachment_type === 'original' ? '#1e40af' : '#64748b' }}>{att.attachment_type}</span>
                        </span>
                        <span style={{ display: 'flex', gap: '8px' }}>
                          <button
                            onClick={async () => {
                              try {
                                const blob = await correspondenceApi.downloadAttachment(att.correspondence_id, att.id)
                                const url = URL.createObjectURL(blob)
                                const a = document.createElement('a'); a.href = url; a.download = att.file_name || 'document'; a.click()
                                URL.revokeObjectURL(url)
                              } catch (err) { toast.error(getErrorMessage(err)) }
                            }}
                            style={{ background: 'none', border: 'none', color: 'var(--primary)', cursor: 'pointer', fontSize: '0.8rem' }}
                          >
                            Download
                          </button>
                          {(corr.status === 'draft' || corr.status === 'received' || corr.status === 'returned') && (
                            <button
                              onClick={() => handleRemoveAttachment(att.id)}
                              disabled={removingAttId === att.id}
                              style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: '0.8rem', opacity: removingAttId === att.id ? 0.5 : 1 }}
                            >
                              {removingAttId === att.id ? 'Removing...' : 'Remove'}
                            </button>
                          )}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <div>
                <label style={labelStyle}>
                  {corr.attachments && corr.attachments.length > 0 ? 'Replace Document' : 'Received Document *'}
                </label>
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
                        onClick={(e) => { e.stopPropagation(); setSelectedFile(null) }}
                        style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: '1rem' }}
                      >
                        ×
                      </button>
                    </div>
                  ) : (
                    <>
                      <p style={{ margin: 0, fontSize: '0.85rem', color: '#334155' }}>
                        Drag &amp; drop or click to upload the received document
                      </p>
                      <p style={{ margin: '4px 0 0', fontSize: '0.75rem', color: '#94a3b8' }}>PDF, DOCX, Excel, Images (max 50 MB)</p>
                    </>
                  )}
                </div>
              </div>
            </div>
          )}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', paddingTop: '8px', borderTop: '1px solid var(--border)' }}>
            <Button variant="secondary" onClick={() => navigate(`/correspondence/${corr.id}`)}>Cancel</Button>
            <Button onClick={handleSave} loading={saving || uploadingFile}>{uploadingFile ? 'Uploading...' : 'Save Changes'}</Button>
          </div>
        </div>
      </div>
    </div>
  )
}
