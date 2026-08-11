import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'react-hot-toast'
import { workflowApi } from '@/api/workflow.api'
import type { Document } from '@/types/document.types'
import type { WorkflowDefinition } from '@/types/workflow.types'

interface Props {
  doc: Document
  categoryId: number
  onClose: () => void
  onSuccess: () => void
}

const overlayStyle: React.CSSProperties = {
  position: 'fixed', inset: 0, zIndex: 1000,
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  background: 'rgba(0,0,0,0.4)',
}

const cardStyle: React.CSSProperties = {
  background: 'var(--surface)', border: '1px solid var(--border)',
  borderRadius: 12, width: '100%', maxWidth: 480,
  maxHeight: '85vh', display: 'flex', flexDirection: 'column', overflow: 'hidden',
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '8px 12px',
  border: '1px solid var(--border)', borderRadius: '8px',
  fontSize: '0.85rem', fontFamily: 'inherit',
  backgroundColor: 'var(--bg)', color: 'var(--text)',
}

export default function SubmitForApprovalModal({ doc, categoryId, onClose, onSuccess }: Props) {
  const navigate = useNavigate()
  const [workflows, setWorkflows] = useState<WorkflowDefinition[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      setLoading(true)
      setError(null)
      try {
        const res = await workflowApi.list({ category_id: categoryId, is_active: true })
        if (cancelled) return
        setWorkflows(res.items)
        if (res.items.length === 1) {
          setSelectedId(res.items[0].id)
        } else if (res.items.length === 0) {
          setError('No active workflows available for this category.')
        }
      } catch {
        if (!cancelled) setError('Failed to load workflows.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [categoryId])

  const handleSubmit = async () => {
    if (!selectedId) return
    setSubmitting(true)
    try {
      await workflowApi.submitInstance({
        document_id: doc.id,
        workflow_definition_id: selectedId,
      })
      toast.success('Document submitted for approval')
      onSuccess()
      navigate('/approvals/history')
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Failed to submit document'
      toast.error(msg)
    } finally {
      setSubmitting(false)
    }
  }

  const selected = workflows.find((w) => w.id === selectedId)

  return (
    <div style={overlayStyle} onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} style={cardStyle}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 20px', borderBottom: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ width: '32px', height: '32px', borderRadius: '8px', backgroundColor: '#eff6ff', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2"><path d="M22 2L11 13"/><path d="M22 2L15 22L11 13L2 9L22 2Z"/></svg>
            </div>
            <h2 style={{ margin: 0, fontSize: '1rem', fontWeight: 600, color: 'var(--text)' }}>Submit for Approval</h2>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 20, cursor: 'pointer', color: 'var(--text-secondary)', lineHeight: 1 }}>&times;</button>
        </div>

        {/* Body */}
        <div style={{ padding: '20px', overflowY: 'auto', flex: 1 }}>
          {loading ? (
            <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem' }}>
              <div style={{ width: '24px', height: '24px', border: '3px solid #e2e8f0', borderTopColor: '#4f46e5', borderRadius: '50%', animation: 'spin 0.7s linear infinite' }} />
              <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
            </div>
          ) : error ? (
            <div style={{ textAlign: 'center', padding: '1.5rem' }}>
              <p style={{ color: '#dc2626', fontSize: '0.875rem', margin: 0 }}>{error}</p>
            </div>
          ) : (
            <>
              {/* Document info */}
              <div style={{ marginBottom: '16px' }}>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', margin: '0 0 4px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Document</p>
                <p style={{ fontSize: '0.9rem', color: 'var(--text)', margin: 0, fontWeight: 500 }}>{doc.title}</p>
              </div>

              {/* Workflow selector */}
              <div style={{ marginBottom: '16px' }}>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', margin: '0 0 4px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Workflow</p>
                {workflows.length === 1 ? (
                  <p style={{ fontSize: '0.875rem', color: 'var(--text)', margin: 0, fontWeight: 500 }}>{workflows[0].name}</p>
                ) : (
                  <select
                    value={selectedId ?? ''}
                    onChange={(e) => setSelectedId(Number(e.target.value) || null)}
                    style={inputStyle}
                  >
                    <option value="">Select a workflow…</option>
                    {workflows.map((w) => (
                      <option key={w.id} value={w.id}>{w.name}</option>
                    ))}
                  </select>
                )}
              </div>

              {/* Selected workflow details */}
              {selected && (
                <div style={{ backgroundColor: 'var(--bg)', borderRadius: '8px', border: '1px solid var(--border)', padding: '12px' }}>
                  <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', margin: 0 }}>
                    {selected.description || 'No description'}
                  </p>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', padding: '12px 20px', borderTop: '1px solid var(--border)' }}>
          <button
            onClick={onClose}
            style={{ padding: '7px 14px', borderRadius: '8px', border: '1px solid var(--border)', backgroundColor: 'var(--surface)', color: 'var(--text-secondary)', fontSize: '0.82rem', fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={!selectedId || submitting || !!error}
            style={{
              padding: '7px 14px', borderRadius: '8px', border: 'none',
              backgroundColor: selectedId && !error ? '#1e293b' : '#cbd5e1',
              color: '#fff', fontSize: '0.82rem', fontWeight: 600,
              cursor: selectedId && !error ? 'pointer' : 'not-allowed',
              fontFamily: 'inherit', opacity: submitting ? 0.7 : 1,
            }}
          >
            {submitting ? 'Submitting…' : 'Submit for Approval'}
          </button>
        </div>
      </div>
    </div>
  )
}
