import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'react-hot-toast'
import { workflowApi } from '@/api/workflow.api'
import { useAuthStore } from '@/store/authStore'
import { useWorkflowStore } from '@/store/workflowStore'
import Button from '@/components/ui/Button'
import SignaturePad from '@/components/workflow/SignaturePad'
import type {
  WorkflowInstance,
  ApprovalAction,
} from '@/types/workflow.types'

const LIMIT = 20

const statusColors: Record<string, { bg: string; color: string }> = {
  pending_approval: { bg: '#fef3c7', color: '#92400e' },
  submitted: { bg: '#dbeafe', color: '#1e40af' },
  approved: { bg: '#d1fae5', color: '#065f46' },
  rejected: { bg: '#fee2e2', color: '#991b1b' },
  returned: { bg: '#ffedd5', color: '#9a3412' },
  draft: { bg: '#f1f5f9', color: '#475569' },
  published: { bg: '#ede9fe', color: '#5b21b6' },
  archived: { bg: '#f3f4f6', color: '#374151' },
}

const actionButtons: {
  action: ApprovalAction
  label: string
  color: string
  hoverBg: string
}[] = [
  { action: 'approve', label: 'Approve', color: '#059669', hoverBg: '#047857' },
  { action: 'reject', label: 'Reject', color: '#dc2626', hoverBg: '#b91c1c' },
  { action: 'return', label: 'Return', color: '#d97706', hoverBg: '#b45309' },
]

export default function PendingApprovalPage() {
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const refreshPendingCount = useWorkflowStore((s) => s.refreshPendingCount)

  const [instances, setInstances] = useState<WorkflowInstance[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)

  // Modal state
  const [modalOpen, setModalOpen] = useState(false)
  const [selectedInstance, setSelectedInstance] = useState<WorkflowInstance | null>(null)
  const [selectedAction, setSelectedAction] = useState<ApprovalAction>('approve')
  const [remarks, setRemarks] = useState('')
  const [signatureBlob, setSignatureBlob] = useState<Blob | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const loadPending = useCallback(async () => {
    setLoading(true)
    try {
      const data = await workflowApi.getPendingInstances({
        skip: (page - 1) * LIMIT,
        limit: LIMIT,
      })
      setInstances(data.items)
      setTotal(data.total)
    } catch {
      toast.error('Failed to load pending approvals')
    } finally {
      setLoading(false)
    }
  }, [page])

  useEffect(() => { loadPending() }, [loadPending])

  const totalPages = Math.ceil(total / LIMIT) || 1

  const openActionModal = (instance: WorkflowInstance, action: ApprovalAction) => {
    setSelectedInstance(instance)
    setSelectedAction(action)
    setRemarks('')
    setSignatureBlob(null)
    setModalOpen(true)
  }

  const closeModal = () => {
    setModalOpen(false)
    setSelectedInstance(null)
    setRemarks('')
    setSignatureBlob(null)
  }

  const handleSubmit = async () => {
    if (!selectedInstance) return
    setSubmitting(true)
    try {
      let signatureId: number | null = null
      if (signatureBlob) {
        const file = new File([signatureBlob], `signature-${Date.now()}.png`, { type: 'image/png' })
        const sig = await workflowApi.uploadSignature(file, 'wet_signature')
        signatureId = sig.id
      }

      await workflowApi.actOnInstance(selectedInstance.id, {
        action: selectedAction,
        remarks: remarks.trim() || undefined,
        signature_id: signatureId,
      })

      const label = selectedAction.charAt(0).toUpperCase() + selectedAction.slice(1)
      toast.success(`Document ${label.toLowerCase()}d successfully`)
      closeModal()
      loadPending()
      refreshPendingCount()
    } catch (err: any) {
      const msg = err?.response?.data?.detail || `Failed to ${selectedAction} document`
      toast.error(msg)
    } finally {
      setSubmitting(false)
    }
  }

  const formatDate = (iso: string) => {
    const d = new Date(iso)
    return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
  }

  return (
    <div>
      {/* Header */}
      <div style={{
        backgroundColor: 'var(--surface)', borderRadius: '1rem', border: '1px solid var(--border)',
        padding: '1.25rem 1.5rem', marginBottom: '1.25rem',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem',
      }}>
        <div>
          <h1 style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text)', margin: 0 }}>
            Pending Approvals
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.82rem', margin: '3px 0 0' }}>
            {total} pending item{total !== 1 ? 's' : ''} awaiting your review
          </p>
        </div>
      </div>

      {/* Main table card */}
      <div style={{
        backgroundColor: 'var(--surface)', borderRadius: '1rem',
        border: '1px solid var(--border)', overflow: 'hidden',
      }}>
        {loading ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '200px' }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{
                width: '28px', height: '28px', border: '3px solid #e2e8f0', borderTopColor: '#4f46e5',
                borderRadius: '50%', animation: 'spin 0.7s linear infinite', margin: '0 auto 0.75rem',
              }} />
              <p style={{ color: 'var(--text-tertiary)', fontSize: '0.875rem', margin: 0 }}>Loading…</p>
            </div>
            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
          </div>
        ) : instances.length === 0 ? (
          <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            justifyContent: 'center', height: '200px', textAlign: 'center',
          }}>
            <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="#e2e8f0" strokeWidth="1.5" style={{ marginBottom: '1rem' }}>
              <path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
            </svg>
            <p style={{ fontWeight: 600, color: 'var(--text-tertiary)', margin: 0 }}>
              No pending approvals
            </p>
            <p style={{ color: 'var(--text-tertiary)', fontSize: '0.82rem', margin: '6px 0 0' }}>
              All caught up — nothing needs your review right now.
            </p>
          </div>
        ) : (
          <>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)' }}>
                    {['Document', 'Workflow', 'Step', 'Submitted By', 'Date', 'Actions'].map((h) => (
                      <th key={h} style={{
                        textAlign: 'left', padding: '0.75rem 1rem', fontWeight: 600,
                        color: 'var(--text-secondary)', fontSize: '0.78rem', textTransform: 'uppercase',
                        letterSpacing: '0.03em', whiteSpace: 'nowrap',
                      }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {instances.map((inst) => {
                    const sc = statusColors[inst.status] || statusColors.draft
                    return (
                      <tr key={inst.id} style={{ borderBottom: '1px solid var(--border)' }}>
                        <td style={{ padding: '0.75rem 1rem', color: 'var(--text)', fontWeight: 500, maxWidth: '220px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {inst.document_title || `Document #${inst.document_id}`}
                        </td>
                        <td style={{ padding: '0.75rem 1rem', color: 'var(--text-secondary)' }}>
                          {inst.workflow_name || '—'}
                        </td>
                        <td style={{ padding: '0.75rem 1rem' }}>
                          <span style={{
                            display: 'inline-block', padding: '2px 10px', borderRadius: '999px',
                            backgroundColor: sc.bg, color: sc.color, fontSize: '0.78rem', fontWeight: 600,
                          }}>
                            {inst.current_step_name || `Step ${inst.current_step_order}`}
                          </span>
                        </td>
                        <td style={{ padding: '0.75rem 1rem', color: 'var(--text-secondary)' }}>
                          {inst.submitted_by_name || '—'}
                        </td>
                        <td style={{ padding: '0.75rem 1rem', color: 'var(--text-tertiary)', whiteSpace: 'nowrap' }}>
                          {formatDate(inst.submitted_at)}
                        </td>
                        <td style={{ padding: '0.75rem 1rem' }}>
                          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                            {actionButtons.map((ab) => (
                              <button
                                key={ab.action}
                                onClick={() => openActionModal(inst, ab.action)}
                                style={{
                                  padding: '4px 12px', borderRadius: '6px', border: 'none',
                                  backgroundColor: ab.color, color: '#fff', fontSize: '0.78rem',
                                  fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit',
                                  transition: 'background-color 150ms',
                                }}
                                onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.backgroundColor = ab.hoverBg }}
                                onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.backgroundColor = ab.color }}
                              >
                                {ab.label}
                              </button>
                            ))}
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                gap: '0.5rem', padding: '1rem', borderTop: '1px solid var(--border)',
              }}>
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  style={pageBtn}
                >
                  ←
                </button>
                <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                  Page {page} of {totalPages}
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  style={pageBtn}
                >
                  →
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {/* Action Modal */}
      {modalOpen && selectedInstance && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 1000,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          backgroundColor: 'rgba(0,0,0,0.4)', backdropFilter: 'blur(2px)',
        }} onClick={(e) => { if (e.target === e.currentTarget) closeModal() }}>
          <div style={{
            backgroundColor: 'var(--surface)', borderRadius: '1rem', border: '1px solid var(--border)',
            width: '100%', maxWidth: '520px', maxHeight: '90vh', overflow: 'auto',
            boxShadow: '0 20px 60px rgba(0,0,0,0.15)',
          }}>
            {/* Modal header */}
            <div style={{
              padding: '1.25rem 1.5rem', borderBottom: '1px solid var(--border)',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            }}>
              <h2 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text)', margin: 0 }}>
                {selectedAction.charAt(0).toUpperCase() + selectedAction.slice(1)} Document
              </h2>
              <button
                onClick={closeModal}
                style={{
                  background: 'none', border: 'none', cursor: 'pointer', padding: '4px',
                  color: 'var(--text-tertiary)', display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>

            {/* Modal body */}
            <div style={{ padding: '1.25rem 1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div>
                <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', margin: '0 0 4px' }}>
                  Document
                </p>
                <p style={{ fontSize: '0.88rem', color: 'var(--text)', fontWeight: 600, margin: 0 }}>
                  {selectedInstance.document_title || `Document #${selectedInstance.document_id}`}
                </p>
              </div>

              {/* Remarks */}
              <div>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text)', marginBottom: '6px' }}>
                  Remarks <span style={{ fontWeight: 400, color: 'var(--text-tertiary)' }}>(optional)</span>
                </label>
                <textarea
                  value={remarks}
                  onChange={(e) => setRemarks(e.target.value)}
                  placeholder="Add any notes or comments…"
                  rows={3}
                  style={{
                    width: '100%', padding: '10px 12px', borderRadius: '8px',
                    border: '1px solid var(--border)', backgroundColor: 'var(--bg, #f8fafc)',
                    color: 'var(--text)', fontSize: '0.85rem', fontFamily: 'inherit',
                    resize: 'vertical', boxSizing: 'border-box',
                  }}
                />
              </div>

              {/* Signature */}
              <div>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text)', marginBottom: '6px' }}>
                  Signature <span style={{ fontWeight: 400, color: 'var(--text-tertiary)' }}>(optional)</span>
                </label>
                {signatureBlob ? (
                  <div style={{
                    padding: '0.75rem', borderRadius: '8px', border: '1px solid var(--border)',
                    backgroundColor: '#f0fdf4',
                  }}>
                    <img
                      src={URL.createObjectURL(signatureBlob)}
                      alt="Signature preview"
                      style={{ maxHeight: 80, display: 'block', marginBottom: '0.5rem' }}
                    />
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#059669" strokeWidth="2">
                        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" />
                      </svg>
                      <span style={{ fontSize: '0.78rem', color: '#065f46', fontWeight: 500 }}>Signature captured</span>
                      <button
                        onClick={() => setSignatureBlob(null)}
                        style={{
                          marginLeft: 'auto', padding: '2px 8px', borderRadius: '4px', border: '1px solid #d1d5db',
                          backgroundColor: '#fff', color: '#6b7280', fontSize: '0.78rem', cursor: 'pointer',
                          fontFamily: 'inherit',
                        }}
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                ) : (
                  <SignaturePad
                    width={460}
                    height={140}
                    onCapture={(blob) => setSignatureBlob(blob)}
                  />
                )}
              </div>
            </div>

            {/* Modal footer */}
            <div style={{
              padding: '1rem 1.5rem', borderTop: '1px solid var(--border)',
              display: 'flex', justifyContent: 'flex-end', gap: '0.5rem',
            }}>
              <Button variant="secondary" onClick={closeModal} disabled={submitting}>
                Cancel
              </Button>
              <Button
                variant={selectedAction === 'approve' ? 'primary' : selectedAction === 'reject' ? 'danger' : 'secondary'}
                loading={submitting}
                onClick={handleSubmit}
              >
                {selectedAction.charAt(0).toUpperCase() + selectedAction.slice(1)}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

const pageBtn: React.CSSProperties = {
  padding: '5px 12px', borderRadius: '7px', border: '1px solid var(--border-soft)',
  backgroundColor: 'var(--surface)', color: 'var(--text-secondary)', fontSize: '0.82rem',
  cursor: 'pointer', fontFamily: 'inherit',
}
