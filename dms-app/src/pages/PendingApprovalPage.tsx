import { useState, useEffect, useCallback } from 'react'
import { toast } from 'react-hot-toast'
import { workflowApi } from '@/api/workflow.api'
import { memoApi } from '@/api/memo.api'
import { documentsApi } from '@/api/documents.api'
import { getErrorMessage } from '@/api/client'
import { useWorkflowStore } from '@/store/workflowStore'
import Button from '@/components/ui/Button'
import type {
  WorkflowInstance,
  ApprovalAction,
} from '@/types/workflow.types'
import type { MemoDetail } from '@/types/memo.types'
import { sanitizeHtml } from '@/utils/sanitizeHtml'

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

export default function PendingApprovalPage() {
  const refreshPendingCount = useWorkflowStore((s) => s.refreshPendingCount)

  const [instances, setInstances] = useState<WorkflowInstance[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)

  // Modal state
  const [modalOpen, setModalOpen] = useState(false)
  const [selectedInstance, setSelectedInstance] = useState<WorkflowInstance | null>(null)
  const [remarks, setRemarks] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [memoDetail, setMemoDetail] = useState<MemoDetail | null>(null)
  const [memoLoading, setMemoLoading] = useState(false)

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

  const openReviewModal = async (instance: WorkflowInstance) => {
    setSelectedInstance(instance)
    setRemarks('')
    setMemoDetail(null)
    setModalOpen(true)

    setMemoLoading(true)
    try {
      const memo = await memoApi.getByDocument(instance.document_id)
      setMemoDetail(memo)
    } catch {
      toast.error('Unable to load memo content')
    } finally {
      setMemoLoading(false)
    }
  }

  const closeModal = () => {
    setModalOpen(false)
    setSelectedInstance(null)
    setRemarks('')
    setMemoDetail(null)
  }

  const handleSubmit = async (action: ApprovalAction) => {
    if (!selectedInstance) return
    setSubmitting(true)
    try {
      await workflowApi.actOnInstance(selectedInstance.id, {
        action,
        remarks: remarks.trim() || undefined,
      })

      const label = action.charAt(0).toUpperCase() + action.slice(1)
      toast.success(`Document ${label.toLowerCase()}d successfully`)
      closeModal()
      loadPending()
      refreshPendingCount()
    } catch (err: any) {
      const msg = err?.response?.data?.detail || `Failed to ${action} document`
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
                          <button
                            onClick={() => openReviewModal(inst)}
                            style={{
                              padding: '5px 16px', borderRadius: '6px', border: '1px solid var(--border)',
                              backgroundColor: 'var(--surface)', color: 'var(--text)', fontSize: '0.78rem',
                              fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit',
                            }}
                          >
                            Review
                          </button>
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
            width: '100%', maxWidth: '720px', maxHeight: '90vh', overflow: 'auto',
            boxShadow: '0 20px 60px rgba(0,0,0,0.15)',
          }}>
            {/* Modal header */}
            <div style={{
              padding: '1.25rem 1.5rem', borderBottom: '1px solid var(--border)',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            }}>
              <h2 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text)', margin: 0 }}>
                Review Document
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

              {/* Memo Content */}
              {memoLoading ? (
                <div style={{ textAlign: 'center', padding: '1rem', color: 'var(--text-tertiary)', fontSize: '0.82rem' }}>
                  Loading memo content…
                </div>
              ) : memoDetail ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  <div>
                    <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', margin: '0 0 4px' }}>Subject</p>
                    <p style={{ fontSize: '0.88rem', color: 'var(--text)', fontWeight: 600, margin: 0 }}>{memoDetail.subject}</p>
                  </div>
                  <div>
                    <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', margin: '0 0 4px' }}>Content</p>
                    <div
                      className="memo-body"
                      style={{
                        padding: '0.75rem', borderRadius: '8px', border: '1px solid var(--border)',
                        backgroundColor: 'var(--bg, #f8fafc)', maxHeight: '300px', overflowY: 'auto',
                        lineHeight: 1.7, fontSize: '0.88rem', color: '#1e293b',
                      }}
                      dangerouslySetInnerHTML={{
                        __html: sanitizeHtml(memoDetail.body)
                      }}
                    />
                  </div>
                  {memoDetail.attachments.length > 0 && (
                    <div>
                      <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', margin: '0 0 4px' }}>
                        Attachments ({memoDetail.attachments.length})
                      </p>
                      <ul style={{ margin: 0, paddingLeft: 0, listStyle: 'none' }}>
                        {memoDetail.attachments.map((a) => (
                          <li key={a.id} style={{
                            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                            padding: '0.4rem 0.6rem', borderRadius: '6px', border: '1px solid var(--border)',
                            backgroundColor: 'var(--bg, #f8fafc)', marginBottom: '0.35rem',
                          }}>
                            <span style={{ fontSize: '0.82rem' }}>
                              <strong>{a.document_title || a.file_name}</strong>{' '}
                              <span style={{ color: 'var(--text-tertiary)', fontWeight: 400 }}>
                                ({a.file_type?.toUpperCase()}, {(a.file_size || 0) / 1024} KB)
                              </span>
                            </span>
                            <button
                              onClick={async () => {
                                try {
                                  await documentsApi.download(a.document_id, a.file_name || a.document_title || 'download')
                                } catch (err) {
                                  toast.error(getErrorMessage(err))
                                }
                              }}
                              style={{ fontSize: '0.78rem', color: '#4f46e5', background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'inherit', padding: 0 }}
                            >
                              Download
                            </button>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ) : null}

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
                variant="secondary"
                loading={submitting}
                onClick={() => handleSubmit('return')}
              >
                Return
              </Button>
              <Button
                variant="danger"
                loading={submitting}
                onClick={() => handleSubmit('reject')}
              >
                Reject
              </Button>
              <Button
                variant="primary"
                loading={submitting}
                onClick={() => handleSubmit('approve')}
              >
                Approve
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
