import { useState, useEffect } from 'react'
import { toast } from 'react-hot-toast'
import { workflowApi } from '@/api/workflow.api'
import { correspondenceApi } from '@/api/correspondence.api'
import type { CorrespondenceDirection } from '@/types/correspondence.types'

interface CorrespondenceSubmitDialogProps {
  isOpen: boolean
  correspondenceId: number
  direction: CorrespondenceDirection
  onClose: () => void
  onSuccess: () => void
}

const DOCUMENT_TYPE_MAP: Record<CorrespondenceDirection, string> = {
  inbound: 'correspondence_inbound',
  outbound: 'correspondence_outbound',
  internal: 'correspondence_internal',
}

export default function CorrespondenceSubmitDialog({
  isOpen,
  correspondenceId,
  direction,
  onClose,
  onSuccess,
}: CorrespondenceSubmitDialogProps) {
  const [workflows, setWorkflows] = useState<Array<{ id: number; name: string }>>([])
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<number | ''>('')
  const [loading, setLoading] = useState(false)
  const [loadingWorkflows, setLoadingWorkflows] = useState(false)

  useEffect(() => {
    if (!isOpen) return
    setSelectedWorkflowId('')
    setLoadingWorkflows(true)
    const docType = DOCUMENT_TYPE_MAP[direction]
    workflowApi
      .list({ is_active: true, document_type: docType })
      .then((res) => {
        setWorkflows(res.items.map((w) => ({ id: w.id, name: w.name })))
      })
      .catch(() => {
        toast.error('Failed to load workflows')
      })
      .finally(() => setLoadingWorkflows(false))
  }, [isOpen, direction])

  const handleSubmit = async () => {
    if (!selectedWorkflowId) return
    setLoading(true)
    try {
      await correspondenceApi.submit(correspondenceId, {
        workflow_definition_id: Number(selectedWorkflowId),
      })
      toast.success('Correspondence submitted for approval')
      onSuccess()
      onClose()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to submit correspondence'
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem' }}>
      <div style={{ position: 'absolute', inset: 0, backgroundColor: 'rgba(15,23,42,0.45)', backdropFilter: 'blur(2px)' }} onClick={onClose} />
      <div style={{ position: 'relative', width: '100%', maxWidth: '440px', backgroundColor: 'var(--surface)', borderRadius: '1rem', boxShadow: '0 20px 60px rgba(0,0,0,0.15)', border: '1px solid var(--border)', overflow: 'hidden' }}>

        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '1.1rem 1.25rem', borderBottom: '1px solid var(--border)' }}>
          <h2 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text)', margin: 0 }}>
            Submit for Approval
          </h2>
          <button onClick={onClose} style={{ width: '32px', height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '8px', border: 'none', backgroundColor: 'transparent', cursor: 'pointer', color: 'var(--text-tertiary)' }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: '1.25rem' }}>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1rem', marginTop: 0 }}>
            Select a workflow to route this correspondence for approval.
          </p>

          {loadingWorkflows ? (
            <div style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--text-tertiary)', fontSize: '0.85rem' }}>
              Loading workflows...
            </div>
          ) : workflows.length === 0 ? (
            <div style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--text-tertiary)', fontSize: '0.85rem', backgroundColor: 'var(--bg)', borderRadius: '8px', border: '1px dashed var(--border)' }}>
              No active workflows found for this correspondence type.
            </div>
          ) : (
            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
                Workflow
              </label>
              <select
                className="input"
                value={selectedWorkflowId}
                onChange={(e) => setSelectedWorkflowId(Number(e.target.value) || '')}
                disabled={loading}
              >
                <option value="">Select workflow</option>
                {workflows.map((w) => (
                  <option key={w.id} value={w.id}>{w.name}</option>
                ))}
              </select>
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{ display: 'flex', gap: '0.75rem', padding: '0 1.25rem 1.25rem' }}>
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            style={{ flex: 1, padding: '0.625rem', backgroundColor: 'var(--bg)', color: 'var(--text-secondary)', border: '1px solid var(--border-soft)', borderRadius: '0.5rem', fontSize: '0.875rem', fontWeight: 500, cursor: 'pointer', fontFamily: 'inherit' }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={loading || !selectedWorkflowId || loadingWorkflows}
            style={{ flex: 1, padding: '0.625rem', backgroundColor: 'var(--text)', color: 'var(--surface)', border: 'none', borderRadius: '0.5rem', fontSize: '0.875rem', fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px', opacity: !selectedWorkflowId || loading ? 0.6 : 1 }}
          >
            {loading ? 'Submitting...' : 'Submit'}
          </button>
        </div>
      </div>
    </div>
  )
}
