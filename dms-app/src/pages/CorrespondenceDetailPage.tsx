import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { correspondenceApi } from '@/api/correspondence.api'
import type { CorrespondenceDetail, DispatchMethod } from '@/types/correspondence.types'
import CorrespondenceTimeline from '@/components/correspondence/CorrespondenceTimeline'
import CorrespondenceResponsePanel from '@/components/correspondence/CorrespondenceResponsePanel'
import CorrespondenceDispatchDialog from '@/components/correspondence/CorrespondenceDispatchDialog'
import CorrespondenceAssignDialog from '@/components/correspondence/CorrespondenceAssignDialog'
import Button from '@/components/ui/Button'
import { formatDateTime } from '@/utils/formatters'
import { getErrorMessage } from '@/api/client'
import { useAuthStore } from '@/store/authStore'

const PRIORITY_BADGES: Record<string, { bg: string; color: string }> = {
  low: { bg: '#f1f5f9', color: '#64748b' }, normal: { bg: '#dbeafe', color: '#1e40af' },
  high: { bg: '#ffedd5', color: '#c2410c' }, urgent: { bg: '#fee2e2', color: '#dc2626' },
}

const STATUS_BADGES: Record<string, { bg: string; color: string }> = {
  draft: { bg: '#f1f5f9', color: '#64748b' }, received: { bg: '#dbeafe', color: '#1e40af' },
  submitted: { bg: '#e0e7ff', color: '#3730a3' }, pending_approval: { bg: '#fef3c7', color: '#92400e' },
  approved: { bg: '#d1fae5', color: '#065f46' }, dispatched: { bg: '#e0e7ff', color: '#3730a3' },
  delivered: { bg: '#d1fae5', color: '#065f46' }, completed: { bg: '#d1fae5', color: '#065f46' },
  cancelled: { bg: '#f1f5f9', color: '#64748b' }, archived: { bg: '#f1f5f9', color: '#64748b' },
  rejected: { bg: '#fee2e2', color: '#dc2626' }, returned: { bg: '#ffedd5', color: '#c2410c' },
}

const sectionCard: React.CSSProperties = {
  padding: '16px', borderRadius: '8px', border: '1px solid var(--border)',
  backgroundColor: 'var(--surface)',
}

export default function CorrespondenceDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [corr, setCorr] = useState<CorrespondenceDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [dispatchOpen, setDispatchOpen] = useState(false)
  const [assignOpen, setAssignOpen] = useState(false)
  const [forwardOpen, setForwardOpen] = useState(false)
  const user = useAuthStore(s => s.user)

  const fetchCorr = async () => {
    if (!id) return
    setLoading(true)
    try {
      const data = await correspondenceApi.get(Number(id))
      setCorr(data)
    } catch (err) {
      toast.error(getErrorMessage(err))
      navigate('/correspondence')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchCorr() }, [id])

  const handleDispatch = async (data: { dispatch_method: DispatchMethod; dispatch_reference?: string; remarks?: string }) => {
    if (!corr) return
    await correspondenceApi.dispatch(corr.id, data)
    toast.success('Correspondence dispatched')
    fetchCorr()
  }

  const handleAssign = async (data: { to_user_id: number; remarks?: string }) => {
    if (!corr) return
    await correspondenceApi.assign(corr.id, data)
    toast.success('Correspondence assigned')
    fetchCorr()
  }

  const handleForward = async (data: { to_user_id: number; remarks?: string }) => {
    if (!corr) return
    await correspondenceApi.forward(corr.id, data)
    toast.success('Correspondence forwarded')
    fetchCorr()
  }

  const handleDeliver = async () => {
    if (!corr) return
    await correspondenceApi.deliver(corr.id)
    toast.success('Marked as delivered')
    fetchCorr()
  }

  const handleAcknowledge = async () => {
    if (!corr) return
    await correspondenceApi.acknowledge(corr.id)
    toast.success('Marked as acknowledged')
    fetchCorr()
  }

  const handleDownloadFinal = async () => {
    if (!corr) return
    try {
      const blob = await correspondenceApi.downloadFinal(corr.id)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${corr.reference_number}_final.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      toast.error(getErrorMessage(err))
    }
  }

  if (loading || !corr) {
    return <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-tertiary)' }}>Loading...</div>
  }

  const pBadge = PRIORITY_BADGES[corr.priority] ?? PRIORITY_BADGES.normal
  const sBadge = STATUS_BADGES[corr.status] ?? STATUS_BADGES.draft
  const isAdmin = user?.roles?.some(r => r.name === 'admin' || r.name === 'superadmin')
  const canEdit = corr.status === 'draft' || corr.status === 'received' || corr.status === 'returned'
  const canDispatch = (corr.status === 'approved' || corr.status === 'ready_for_dispatch') && isAdmin
  const canDeliver = corr.status === 'dispatched' && isAdmin
  const canAcknowledge = corr.status === 'delivered' && isAdmin

  return (
    <div style={{ padding: '1.5rem', maxWidth: '1200px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.5rem' }}>
        <div>
          <button onClick={() => navigate('/correspondence')} style={{ background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer', fontSize: '0.82rem', marginBottom: '4px' }}>← Back to Correspondence</button>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--text)', margin: 0 }}>{corr.reference_number}</h1>
          <div style={{ display: 'flex', gap: '8px', marginTop: '8px', alignItems: 'center' }}>
            <span style={{ display: 'inline-block', padding: '2px 8px', borderRadius: '999px', fontSize: '0.7rem', fontWeight: 600, backgroundColor: corr.direction === 'inbound' ? '#dbeafe' : corr.direction === 'outbound' ? '#d1fae5' : '#fef3c7', color: corr.direction === 'inbound' ? '#1e40af' : corr.direction === 'outbound' ? '#065f46' : '#92400e' }}>{corr.direction.toUpperCase()}</span>
            <span style={{ display: 'inline-block', padding: '2px 8px', borderRadius: '999px', fontSize: '0.7rem', fontWeight: 600, backgroundColor: pBadge.bg, color: pBadge.color }}>{corr.priority}</span>
            <span style={{ display: 'inline-block', padding: '2px 8px', borderRadius: '999px', fontSize: '0.7rem', fontWeight: 600, backgroundColor: sBadge.bg, color: sBadge.color }}>{corr.status.replace(/_/g, ' ')}</span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          {canEdit && <Button variant="outline" size="sm" onClick={() => navigate(`/correspondence/${corr.id}/edit`)}>Edit</Button>}
          {canDispatch && <Button size="sm" onClick={() => setDispatchOpen(true)}>Dispatch</Button>}
          {canDeliver && <Button size="sm" onClick={handleDeliver}>Mark Delivered</Button>}
          {canAcknowledge && <Button size="sm" onClick={handleAcknowledge}>Mark Acknowledged</Button>}
          {corr.status === 'approved' && <Button variant="accent" size="sm" onClick={handleDownloadFinal}>Download PDF</Button>}
        </div>
      </div>

      {/* Two-column layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: '1.5rem' }}>
        {/* Left column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {/* Subject */}
          <div style={sectionCard}>
            <h3 style={{ margin: '0 0 8px', fontSize: '0.95rem', color: 'var(--text)' }}>{corr.subject}</h3>
            {corr.body && (
              <div
                dangerouslySetInnerHTML={{ __html: corr.body }}
                style={{ fontSize: '0.85rem', lineHeight: 1.6, color: 'var(--text-secondary)' }}
              />
            )}
          </div>

          {/* Attachments */}
          {corr.attachments && corr.attachments.length > 0 && (
            <div style={sectionCard}>
              <h4 style={{ margin: '0 0 8px', fontSize: '0.85rem', color: 'var(--text)' }}>Attachments</h4>
              <ul style={{ margin: 0, paddingLeft: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {corr.attachments.map(att => (
                  <li key={att.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 10px', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 6, fontSize: '0.8rem' }}>
                    <span>
                      <strong>{att.file_name}</strong>{' '}
                      <span style={{ color: '#64748b' }}>({att.file_type?.toUpperCase()}, {att.file_size != null ? `${(att.file_size / 1024).toFixed(1)} KB` : '—'})</span>
                      <span style={{ marginLeft: 6, padding: '1px 6px', borderRadius: 4, fontSize: '0.7rem', background: att.attachment_type === 'original' ? '#dbeafe' : '#f1f5f9', color: att.attachment_type === 'original' ? '#1e40af' : '#64748b' }}>{att.attachment_type}</span>
                    </span>
                    <button
                      onClick={async () => {
                        try {
                          const blob = await correspondenceApi.download(att.correspondence_id)
                          const url = URL.createObjectURL(blob)
                          const a = document.createElement('a'); a.href = url; a.download = att.file_name || 'attachment'; a.click()
                          URL.revokeObjectURL(url)
                        } catch (err) { toast.error(getErrorMessage(err)) }
                      }}
                      style={{ background: 'none', border: 'none', color: 'var(--primary)', cursor: 'pointer', fontSize: '0.8rem' }}
                    >
                      Download
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Sender / Recipient */}
          {(corr.sender_name || corr.recipient_name) && (
            <div style={sectionCard}>
              <h4 style={{ margin: '0 0 8px', fontSize: '0.85rem', color: 'var(--text)' }}>
                {corr.direction === 'inbound' ? 'Sender' : 'Recipient'}
              </h4>
              {corr.direction === 'inbound' ? (
                <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                  {corr.sender_name && <div><strong>{corr.sender_name}</strong></div>}
                  {corr.sender_organization && <div>{corr.sender_organization}</div>}
                  {corr.sender_email && <div>{corr.sender_email}</div>}
                  {corr.sender_phone && <div>{corr.sender_phone}</div>}
                </div>
              ) : (
                <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                  {corr.recipient_name && <div><strong>{corr.recipient_name}</strong></div>}
                  {corr.recipient_organization && <div>{corr.recipient_organization}</div>}
                  {corr.recipient_email && <div>{corr.recipient_email}</div>}
                  {corr.recipient_phone && <div>{corr.recipient_phone}</div>}
                </div>
              )}
            </div>
          )}

          {/* Response panel */}
          <CorrespondenceResponsePanel correspondence={corr} />

          {/* Dispatch info */}
          {corr.dispatch_method && (
            <div style={sectionCard}>
              <h4 style={{ margin: '0 0 8px', fontSize: '0.85rem', color: 'var(--text)' }}>Dispatch Information</h4>
              <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                <div>Method: <strong>{corr.dispatch_method}</strong></div>
                {corr.dispatched_at && <div>Date: {formatDateTime(corr.dispatched_at)}</div>}
                {corr.dispatch_reference && <div>Reference: {corr.dispatch_reference}</div>}
                {corr.delivered_at && <div>Delivered: {formatDateTime(corr.delivered_at)}</div>}
                {corr.acknowledged_at && <div>Acknowledged: {formatDateTime(corr.acknowledged_at)}</div>}
              </div>
            </div>
          )}
        </div>

        {/* Right column (sidebar) */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {/* Metadata */}
          <div style={sectionCard}>
            <h4 style={{ margin: '0 0 8px', fontSize: '0.85rem', color: 'var(--text)' }}>Details</h4>
            <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <div>Created by: <strong>{corr.created_by_name || '—'}</strong></div>
              <div>Created: {formatDateTime(corr.created_at)}</div>
              <div>Updated: {formatDateTime(corr.updated_at)}</div>
              {corr.category_name && <div>Category: <strong>{corr.category_name}</strong></div>}
              {corr.date_received && <div>Received: {formatDateTime(corr.date_received)}</div>}
              {corr.date_sent && <div>Sent: {formatDateTime(corr.date_sent)}</div>}
              {corr.workflow_status && <div>Workflow: <strong>{corr.workflow_status}</strong></div>}
            </div>
          </div>

          {/* Actions */}
          <div style={sectionCard}>
            <h4 style={{ margin: '0 0 8px', fontSize: '0.85rem', color: 'var(--text)' }}>Actions</h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {isAdmin && (
                <>
                  <Button variant="outline" size="sm" fullWidth onClick={() => setAssignOpen(true)}>Assign</Button>
                  <Button variant="outline" size="sm" fullWidth onClick={() => setForwardOpen(true)}>Forward</Button>
                </>
              )}
              {corr.document_id && (
                <Button variant="ghost" size="sm" fullWidth onClick={async () => {
                  try {
                    const blob = await correspondenceApi.download(corr.id)
                    const url = URL.createObjectURL(blob)
                    const a = document.createElement('a'); a.href = url; a.download = corr.file_name || 'document'; a.click()
                    URL.revokeObjectURL(url)
                  } catch (err) { toast.error(getErrorMessage(err)) }
                }}>Download Original</Button>
              )}
            </div>
          </div>

          {/* Movements */}
          <div style={sectionCard}>
            <h4 style={{ margin: '0 0 8px', fontSize: '0.85rem', color: 'var(--text)' }}>Movement History</h4>
            <CorrespondenceTimeline movements={corr.movements || []} />
          </div>
        </div>
      </div>

      {/* Dialogs */}
      <CorrespondenceDispatchDialog isOpen={dispatchOpen} onClose={() => setDispatchOpen(false)} onConfirm={handleDispatch} />
      <CorrespondenceAssignDialog isOpen={assignOpen} onClose={() => setAssignOpen(false)} onConfirm={handleAssign} />
      <CorrespondenceAssignDialog isOpen={forwardOpen} onClose={() => setForwardOpen(false)} onConfirm={handleForward} />
    </div>
  )
}
