import { useState, useEffect } from 'react'
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
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', paddingTop: '8px', borderTop: '1px solid var(--border)' }}>
            <Button variant="secondary" onClick={() => navigate(`/correspondence/${corr.id}`)}>Cancel</Button>
            <Button onClick={handleSave} loading={saving}>Save Changes</Button>
          </div>
        </div>
      </div>
    </div>
  )
}
