import { useState, useEffect, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import { toast } from 'react-hot-toast'
import { memoApi } from '@/api/memo.api'
import { workflowApi } from '@/api/workflow.api'
import type { MemoDetail } from '@/types/memo.types'
import type { WorkflowInstanceDetail, ApprovalAction, WorkflowActionCreate } from '@/types/workflow.types'
import Button from '@/components/ui/Button'
import SignaturePad from '@/components/workflow/SignaturePad'
import { useAuthStore } from '@/store/authStore'

const STATUS_COLORS: Record<string, { bg: string; color: string }> = {
  draft: { bg: '#f1f5f9', color: '#475569' },
  submitted: { bg: '#dbeafe', color: '#1e40af' },
  pending_approval: { bg: '#fef3c7', color: '#92400e' },
  approved: { bg: '#d1fae5', color: '#065f46' },
  rejected: { bg: '#fee2e2', color: '#991b1b' },
  returned: { bg: '#ffedd5', color: '#9a3412' },
  published: { bg: '#ede9fe', color: '#5b21b6' },
  archived: { bg: '#f3f4f6', color: '#374151' },
}

export default function MemoDetailPage() {
  const { id } = useParams<{ id: string }>()
  const memoId = Number(id)
  const hasRole = useAuthStore((s) => s.hasRole)
  const isMaker = hasRole('maker')

  const [memo, setMemo] = useState<MemoDetail | null>(null)
  const [instance, setInstance] = useState<WorkflowInstanceDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [actionModal, setActionModal] = useState<{ open: boolean; instanceId?: number }>({ open: false })
  const [selectedAction, setSelectedAction] = useState<ApprovalAction>('approve')
  const [remarks, setRemarks] = useState('')
  const [signatureId, setSignatureId] = useState<number | null>(null)
  const [acting, setActing] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const authorSigUrlRef = useRef<string>('')
  const [authorSigUrl, setAuthorSigUrl] = useState<string>('')

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      try {
        const m = await memoApi.get(memoId)
        setMemo(m)
        if (m.workflow_status) {
          const inst = await workflowApi.getInstanceByDocument(m.document_id)
          setInstance(inst)
        }
      } catch {
        toast.error('Failed to load memo')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [memoId])

  useEffect(() => {
    if (!memo?.author_signature_id) return
    let revoked = false
    workflowApi.getSignatureFileUrl(memo.author_signature_id).then((url) => {
      if (!revoked) {
        authorSigUrlRef.current = url
        setAuthorSigUrl(url)
      }
    }).catch(() => {})
    return () => {
      revoked = true
      if (authorSigUrlRef.current) {
        URL.revokeObjectURL(authorSigUrlRef.current)
        authorSigUrlRef.current = ''
      }
    }
  }, [memo?.author_signature_id])

  const statusColor = (status: string | null) => STATUS_COLORS[status || 'draft'] || STATUS_COLORS.draft

  const handleAct = async () => {
    if (!instance) return
    setActing(true)
    try {
      const payload: WorkflowActionCreate = {
        action: selectedAction,
        remarks,
        signature_id: signatureId || undefined,
      }
      await workflowApi.actOnInstance(instance.id, payload)
      toast.success(`Memo ${selectedAction}d`)
      setActionModal({ open: false })
      setRemarks('')
      setSignatureId(null)
      const inst = await workflowApi.getInstanceByDocument(memo!.document_id)
      setInstance(inst)
      const m = await memoApi.get(memoId)
      setMemo(m)
    } catch (err: any) {
      const message = err?.response?.data?.detail || `Failed to ${selectedAction}`
      toast.error(message)
    } finally {
      setActing(false)
    }
  }

  const handleSignatureCapture = async (blob: Blob) => {
    const file = new File([blob], 'signature.png', { type: 'image/png' })
    try {
      const sig = await workflowApi.uploadSignature(file, 'e_signature')
      setSignatureId(sig.id)
    } catch {
      toast.error('Failed to upload signature')
    }
  }

  const handleDownloadDraft = async () => {
    setDownloading(true)
    try {
      const blob = await memoApi.downloadFinalDraft(memoId)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `memo_${memoId}_final_draft.pdf`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (err: any) {
      const message = err?.response?.data?.detail || 'Failed to download final draft'
      toast.error(message)
    } finally {
      setDownloading(false)
    }
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '3rem' }}>Loading...</div>
    )
  }

  if (!memo) {
    return (
      <div style={{ textAlign: 'center', padding: '3rem', color: '#64748b' }}>Memo not found</div>
    )
  }

  const isDraft = !memo.workflow_status || ['draft', 'returned'].includes(memo.workflow_status)
  const history = instance?.history ?? []

  return (
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <Link to="/memos" style={{ fontSize: '0.85rem', color: '#4f46e5', textDecoration: 'none', display: 'inline-block', marginBottom: '0.5rem' }}>← Back to Memos</Link>
          <h1 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 600 }}>{memo.subject}</h1>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          {isDraft && (
            <Link to={`/memos/${memo.id}/edit`} style={{ textDecoration: 'none' }}>
              <Button variant="secondary" size="sm">Edit Draft</Button>
            </Link>
          )}
          {memo.workflow_status === 'approved' && (
            <Button
              variant="primary"
              size="sm"
              onClick={handleDownloadDraft}
              disabled={downloading}
            >
              {downloading ? 'Generating...' : 'Download Final Draft'}
            </Button>
          )}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: '1.5rem' }}>
        <div>
          <div style={{ background: 'white', border: '1px solid #e2e8f0', borderRadius: 8, padding: '1.5rem', marginBottom: '1.5rem' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '1rem', marginBottom: '1rem', fontSize: '0.85rem' }}>
              <div><strong style={{ color: '#64748b' }}>Date:</strong> {new Date(memo.memo_date).toLocaleDateString()}</div>
              <div><strong style={{ color: '#64748b' }}>Status:</strong>
                <span
                  style={{
                    display: 'inline-block',
                    marginLeft: '0.5rem',
                    padding: '2px 8px',
                    borderRadius: 9999,
                    fontSize: '0.7rem',
                    fontWeight: 600,
                    ...statusColor(memo.workflow_status),
                  }}
                >
                  {(memo.workflow_status || 'draft').replace('_', ' ').toUpperCase()}
                </span>
              </div>
            </div>
            <hr style={{ border: 'none', borderTop: '1px solid #e2e8f0', margin: '1rem 0' }} />
            <div
              style={{
                lineHeight: 1.7,
                fontSize: '0.95rem',
                color: '#1e293b',
                whiteSpace: 'pre-wrap',
              }}
              dangerouslySetInnerHTML={{
                __html: memo.body
                  .replace(/&/g, '&')
                  .replace(/</g, '<')
                  .replace(/>/g, '>')
                  .replace(/\n/g, '<br>')
                  .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
                  .replace(/\*(.+?)\*/g, '<em>$1</em>')
                  .replace(/`(.+?)`/g, '<code style="background:#f1f5f9;padding:1px 5px;border-radius:4px;font-size:0.9em">$1</code>')
              }}
            />
          </div>

          {memo.attachments.length > 0 && (
            <div style={{ background: 'white', border: '1px solid #e2e8f0', borderRadius: 8, padding: '1.5rem' }}>
              <h3 style={{ margin: '0 0 1rem', fontSize: '0.9rem' }}>Attachments ({memo.attachments.length})</h3>
              <ul style={{ margin: 0, paddingLeft: 0, listStyle: 'none' }}>
                {memo.attachments.map((a) => (
                  <li key={a.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.5rem 0', borderBottom: '1px solid #f1f5f9' }}>
                    <span style={{ fontSize: '0.85rem' }}>
                      <strong>{a.document_title || a.file_name}</strong> {' '}
                      <span style={{ color: '#64748b', fontWeight: 400 }}>({a.file_type?.toUpperCase()}, {(a.file_size || 0) / 1024} KB)</span>
                    </span>
                    <Link
                      to={`/api/v1/documents/${a.document_id}/download`}
                      style={{ fontSize: '0.8rem', color: '#4f46e5' }}
                    >
                      Download
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {memo.author_signature_id && (
            <div style={{ marginTop: '1.5rem', padding: '1rem', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8 }}>
              <h3 style={{ margin: '0 0 0.5rem', fontSize: '0.85rem' }}>Author's Signature</h3>
              {authorSigUrl ? (
                <img
                  src={authorSigUrl}
                  alt="Author signature"
                  style={{ maxWidth: 300, maxHeight: 150, border: '1px solid #e2e8f0', borderRadius: 6 }}
                />
              ) : (
                <p style={{ fontSize: '0.85rem', color: '#94a3b8' }}>Loading…</p>
              )}
            </div>
          )}
        </div>

        <div>
          {instance && (
            <div style={{ background: 'white', border: '1px solid #e2e8f0', borderRadius: 8, padding: '1.5rem', position: 'sticky', top: '1.5rem' }}>
              <h3 style={{ margin: '0 0 1rem', fontSize: '0.9rem' }}>Approval Workflow</h3>
              <div style={{ marginBottom: '1rem' }}>
                <strong style={{ fontSize: '0.85rem' }}>Workflow:</strong>
                <div style={{ fontSize: '0.8rem', color: '#475569' }}>{instance.workflow_name}</div>
              </div>
              <div style={{ marginBottom: '1rem' }}>
                <strong style={{ fontSize: '0.85rem' }}>Current Step:</strong>
                <div style={{ fontSize: '0.8rem', color: '#475569' }}>{instance.current_step_name} (Step {instance.current_step_order})</div>
              </div>
              <div style={{ marginBottom: '1rem' }}>
                <strong style={{ fontSize: '0.85rem' }}>Status:</strong>
                <span
                  style={{
                    display: 'inline-block',
                    marginLeft: '0.5rem',
                    padding: '2px 8px',
                    borderRadius: 9999,
                    fontSize: '0.7rem',
                    fontWeight: 600,
                    ...statusColor(instance.status),
                  }}
                >
                  {instance.status.replace('_', ' ').toUpperCase()}
                </span>
              </div>

              {!isMaker && ['submitted', 'pending_approval', 'returned'].includes(instance.status) && (
                <Button
                  variant="primary"
                  size="sm"
                  style={{ width: '100%' }}
                  onClick={() => setActionModal({ open: true, instanceId: instance.id })}
                >
                  Take Action
                </Button>
              )}

              {history.length > 0 && (
                <div style={{ marginTop: '1.5rem', borderTop: '1px solid #e2e8f0', paddingTop: '1rem' }}>
                  <h4 style={{ margin: '0 0 0.75rem', fontSize: '0.8rem' }}>History</h4>
                  <ul style={{ margin: 0, paddingLeft: 0, listStyle: 'none', fontSize: '0.75rem' }}>
                    {history.map((h) => (
                      <li key={h.id} style={{ marginBottom: '0.5rem', color: '#475569' }}>
                        <strong>{h.event_type.replace('_', ' ').toUpperCase()}</strong> by {h.actor_name}
                        <div style={{ color: '#64748b', fontSize: '0.7rem' }}>
                          {new Date(h.occurred_at).toLocaleString()}
                          {h.remarks && <div style={{ marginTop: '2px', fontStyle: 'italic' }}>{h.remarks}</div>}
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {!instance && isDraft && (
            <div style={{ background: 'white', border: '1px solid #e2e8f0', borderRadius: 8, padding: '1.5rem', position: 'sticky', top: '1.5rem' }}>
              <h3 style={{ margin: '0 0 0.5rem', fontSize: '0.9rem' }}>Submit for Approval</h3>
              <p style={{ margin: '0 0 1rem', fontSize: '0.8rem', color: '#64748b' }}>This memo is a draft. Use the Edit page to submit it through a workflow.</p>
              <Link to={`/memos/${memo.id}/edit`}><Button variant="secondary" size="sm" style={{ width: '100%' }}>Edit & Submit</Button></Link>
            </div>
          )}
        </div>
      </div>

      {actionModal.open && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 12, width: '100%', maxWidth: 480, maxHeight: '85vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <div style={{ padding: '1rem', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ margin: 0, fontSize: '1rem' }}>Take Action</h3>
              <button onClick={() => setActionModal({ open: false })} style={{ background: 'none', border: 'none', fontSize: '1.25rem', cursor: 'pointer' }}>×</button>
            </div>
            <div style={{ padding: '1rem', display: 'flex', flexDirection: 'column', gap: '1rem', overflowY: 'auto' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', marginBottom: '4px' }}>Action</label>
                <select
                  value={selectedAction}
                  onChange={(e) => setSelectedAction(e.target.value as ApprovalAction)}
                  style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
                >
                  <option value="approve">Approve</option>
                  <option value="reject">Reject</option>
                  <option value="return">Return</option>
                </select>
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', marginBottom: '4px' }}>Remarks</label>
                <textarea
                  value={remarks}
                  onChange={(e) => setRemarks(e.target.value)}
                  placeholder="Optional remarks..."
                  rows={3}
                  style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6 }}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', marginBottom: '4px' }}>Signature (optional)</label>
                <SignaturePad onCapture={handleSignatureCapture} onCancel={() => setSignatureId(null)} />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                <Button variant="secondary" size="sm" onClick={() => setActionModal({ open: false })}>Cancel</Button>
                <Button onClick={handleAct} disabled={acting}>{acting ? 'Acting...' : 'Confirm'}</Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
