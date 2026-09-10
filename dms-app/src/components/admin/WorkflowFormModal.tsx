import { useState, useEffect } from 'react'
import { toast } from 'react-hot-toast'
import { workflowApi } from '@/api/workflow.api'
import { usersApi } from '@/api/users.api'
import { getErrorMessage } from '@/api/client'
import { useAuthStore } from '@/store/authStore'
import type { WorkflowDefinitionDetail, WorkflowStepCreate, ApprovalMode } from '@/types/workflow.types'
import type { User, Role } from '@/types/user.types'

interface WorkflowFormModalProps {
  isOpen: boolean
  editing: WorkflowDefinitionDetail | null
  onClose: () => void
  onSuccess: () => void
}

interface StepForm {
  step_name: string
  approval_mode: ApprovalMode
  approvers: ApproverForm[]
}

interface ApproverForm {
  user_id: number | null
  role_id: number | null
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '8px 12px',
  border: '1px solid var(--border)',
  borderRadius: '8px',
  fontSize: '0.85rem',
  fontFamily: 'inherit',
  backgroundColor: 'var(--bg)',
  color: 'var(--text)',
  boxSizing: 'border-box',
}

export default function WorkflowFormModal({ isOpen, editing, onClose, onSuccess }: WorkflowFormModalProps) {
  const isSuperAdmin = useAuthStore((state) => state.isSuperAdmin())
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [steps, setSteps] = useState<StepForm[]>([])
  const [loading, setLoading] = useState(false)
  const [loadingData, setLoadingData] = useState(false)
  const [error, setError] = useState('')
  const [users, setUsers] = useState<User[]>([])
  const [roles, setRoles] = useState<Role[]>([])

  useEffect(() => {
    if (!isOpen) return
    if (isSuperAdmin) {
      onClose()
      return
    }
    usersApi.list({ limit: 200 }).then((res) => setUsers(res.items)).catch(() => {})
    usersApi.listRoles().then(setRoles).catch(() => {})
  }, [isOpen, isSuperAdmin, onClose])

  useEffect(() => {
    if (!isOpen) return
    setError('')
    if (editing) {
      setLoadingData(true)
      workflowApi.get(editing.id).then((detail) => {
        setName(detail.name)
        setDescription(detail.description || '')
        setSteps(
          detail.steps.map((s) => ({
            step_name: s.step_name,
            approval_mode: s.approval_mode,
            approvers: s.approvers.map((a) => ({
              user_id: a.user_id,
              role_id: a.role_id,
            })),
          }))
        )
      }).catch((err) => {
        setError(getErrorMessage(err))
      }).finally(() => {
        setLoadingData(false)
      })
    } else {
      setName('')
      setDescription('')
      setSteps([])
    }
  }, [editing, isOpen])

  const addStep = () => {
    setSteps((prev) => [
      ...prev,
      { step_name: '', approval_mode: 'sequential', approvers: [] },
    ])
  }

  const removeStep = (index: number) => {
    setSteps((prev) => prev.filter((_, i) => i !== index))
  }

  const updateStep = (index: number, field: keyof StepForm, value: string) => {
    setSteps((prev) =>
      prev.map((s, i) => (i === index ? { ...s, [field]: value } : s))
    )
  }

  const addApprover = (stepIndex: number) => {
    setSteps((prev) =>
      prev.map((s, i) =>
        i === stepIndex
          ? { ...s, approvers: [...s.approvers, { user_id: null, role_id: null }] }
          : s
      )
    )
  }

  const removeApprover = (stepIndex: number, approverIndex: number) => {
    setSteps((prev) =>
      prev.map((s, i) =>
        i === stepIndex
          ? { ...s, approvers: s.approvers.filter((_, ai) => ai !== approverIndex) }
          : s
      )
    )
  }

  const updateApprover = (stepIndex: number, approverIndex: number, field: keyof ApproverForm, value: number | null) => {
    setSteps((prev) =>
      prev.map((s, i) => {
        if (i !== stepIndex) return s
        return {
          ...s,
          approvers: s.approvers.map((a, ai) => {
            if (ai !== approverIndex) return a
            if (field === 'user_id') return { ...a, user_id: value as number | null, role_id: null }
            if (field === 'role_id') return { ...a, role_id: value as number | null, user_id: null }
            return { ...a, [field]: value }
          }),
        }
      })
    )
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) { setError('Name is required.'); return }
    if (steps.length === 0) { setError('At least one step is required.'); return }
    for (let i = 0; i < steps.length; i++) {
      if (!steps[i].step_name.trim()) {
        setError(`Step ${i + 1} requires a name.`)
        return
      }
    }

    setLoading(true)
    setError('')
    try {
      const stepsData: WorkflowStepCreate[] = steps.map((s, i) => ({
        step_order: i + 1,
        step_name: s.step_name.trim(),
        approval_mode: s.approval_mode,
        approvers: s.approvers.map((a) => ({
          user_id: a.user_id,
          role_id: a.role_id,
        })),
      }))

      if (editing) {
        await workflowApi.update(editing.id, {
          name: name.trim(),
          description: description.trim() || undefined,
          steps: stepsData,
        })
        toast.success('Workflow updated')
      } else {
        await workflowApi.create({
          name: name.trim(),
          description: description.trim() || undefined,
          steps: stepsData,
        })
        toast.success('Workflow created')
      }
      onSuccess()
      onClose()
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem' }}>
      <div style={{ position: 'absolute', inset: 0, backgroundColor: 'rgba(15,23,42,0.45)', backdropFilter: 'blur(2px)' }} onClick={onClose} />
      <div style={{ position: 'relative', width: '100%', maxWidth: '700px', backgroundColor: 'var(--surface)', borderRadius: '1rem', boxShadow: '0 20px 60px rgba(0,0,0,0.15)', border: '1px solid var(--border)', overflow: 'hidden', maxHeight: '85vh', display: 'flex', flexDirection: 'column' }}>

        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '1.1rem 1.25rem', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ width: '32px', height: '32px', backgroundColor: 'var(--surface-2)', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#475569" strokeWidth="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
            </div>
            <h2 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text)', margin: 0 }}>
              {editing ? 'Edit workflow' : 'New workflow'}
            </h2>
          </div>
          <button onClick={onClose} style={{ width: '32px', height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '8px', border: 'none', backgroundColor: 'transparent', cursor: 'pointer', color: 'var(--text-tertiary)' }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} style={{ padding: '1.25rem', overflowY: 'auto', flex: 1 }}>
          {error && (
            <div style={{ marginBottom: '1rem', padding: '0.75rem', backgroundColor: '#fef2f2', border: '1px solid #fecaca', borderRadius: '0.5rem', color: '#dc2626', fontSize: '0.85rem' }}>
              {error}
            </div>
          )}

          {loadingData ? (
            <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-tertiary)', fontSize: '0.85rem' }}>Loading workflow...</div>
          ) : (
            <>
              <div style={{ marginBottom: '0.75rem' }}>
                <label style={labelStyle}>Name <Req /></label>
                <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Purchase Order Approval" disabled={loading} autoFocus />
              </div>

              <div style={{ marginBottom: '0.75rem' }}>
                <label style={labelStyle}>Description</label>
                <textarea className="input" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Optional description" disabled={loading} rows={2} style={{ resize: 'vertical' }} />
              </div>

              {/* Steps Section */}
              <div style={{ marginBottom: '1rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.6rem' }}>
                  <label style={{ ...labelStyle, marginBottom: 0 }}>Steps <Req /></label>
                  <button type="button" onClick={addStep} disabled={loading} style={{ padding: '4px 10px', fontSize: '0.78rem', fontWeight: 600, color: '#4f46e5', backgroundColor: 'transparent', border: '1px solid #c7d2fe', borderRadius: '6px', cursor: 'pointer', fontFamily: 'inherit', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                    Add Step
                  </button>
                </div>

                {steps.length === 0 && (
                  <div style={{ padding: '1.25rem', textAlign: 'center', color: 'var(--text-tertiary)', fontSize: '0.82rem', backgroundColor: 'var(--bg)', border: '1px dashed var(--border)', borderRadius: '8px' }}>
                    No steps added. Click "Add Step" to define an approval step.
                  </div>
                )}

                {steps.map((step, stepIdx) => (
                  <div key={stepIdx} style={{ marginBottom: '0.75rem', padding: '0.85rem', border: '1px solid var(--border)', borderRadius: '8px', backgroundColor: 'var(--bg)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.6rem' }}>
                      <span style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text)' }}>Step {stepIdx + 1}</span>
                      <button type="button" onClick={() => removeStep(stepIdx)} disabled={loading} style={{ padding: '2px 8px', fontSize: '0.72rem', color: '#dc2626', backgroundColor: 'transparent', border: '1px solid #fecaca', borderRadius: '6px', cursor: 'pointer', fontFamily: 'inherit' }}>
                        Remove
                      </button>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '0.5rem', marginBottom: '0.6rem' }}>
                      <div>
                        <label style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.2rem', display: 'block' }}>Step Name <Req /></label>
                        <input
                          className="input"
                          value={step.step_name}
                          onChange={(e) => updateStep(stepIdx, 'step_name', e.target.value)}
                          placeholder="e.g. Manager Review"
                          disabled={loading}
                        />
                      </div>
                      <div>
                        <label style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.2rem', display: 'block' }}>Approval Mode</label>
                        <select
                          className="input"
                          value={step.approval_mode}
                          onChange={(e) => updateStep(stepIdx, 'approval_mode', e.target.value)}
                          disabled={loading}
                          style={{ minWidth: '130px' }}
                        >
                          <option value="sequential">Sequential</option>
                          <option value="parallel">Parallel</option>
                        </select>
                      </div>
                    </div>

                    {/* Approvers for this step */}
                    <div style={{ marginTop: '0.5rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
                        <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-tertiary)' }}>Approvers</span>
                        <button type="button" onClick={() => addApprover(stepIdx)} disabled={loading} style={{ padding: '2px 8px', fontSize: '0.7rem', color: '#4f46e5', backgroundColor: 'transparent', border: '1px solid #c7d2fe', borderRadius: '6px', cursor: 'pointer', fontFamily: 'inherit' }}>
                          + Add Approver
                        </button>
                      </div>

                      {step.approvers.length === 0 && (
                        <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', fontStyle: 'italic' }}>
                          No approvers assigned. At least one is recommended.
                        </div>
                      )}

                      {step.approvers.map((approver, approverIdx) => (
                        <div key={approverIdx} style={{ display: 'grid', gridTemplateColumns: '1fr 100px 32px', gap: '0.4rem', alignItems: 'end', marginBottom: '0.35rem' }}>
                          <div>
                            <label style={{ fontSize: '0.68rem', fontWeight: 500, color: 'var(--text-tertiary)', marginBottom: '0.15rem', display: 'block' }}>User or Role</label>
                            <select
                              className="input"
                              value={approver.user_id ? `user-${approver.user_id}` : approver.role_id ? `role-${approver.role_id}` : ''}
                              onChange={(e) => {
                                const val = e.target.value
                                if (val.startsWith('user-')) updateApprover(stepIdx, approverIdx, 'user_id', Number(val.split('-')[1]))
                                else if (val.startsWith('role-')) updateApprover(stepIdx, approverIdx, 'role_id', Number(val.split('-')[1]))
                              }}
                              disabled={loading}
                            >
                              <option value="">Select...</option>
                              {roles.length > 0 && (
                                <optgroup label="Roles">
                                  {roles.map((r) => (
                                    <option key={`role-${r.id}`} value={`role-${r.id}`}>{r.name}</option>
                                  ))}
                                </optgroup>
                              )}
                              {users.length > 0 && (
                                <optgroup label="Users">
                                  {users.filter((u) => u.is_active).map((u) => (
                                    <option key={`user-${u.id}`} value={`user-${u.id}`}>{u.full_name || u.email}</option>
                                  ))}
                                </optgroup>
                              )}
                            </select>
                          </div>
                          <div>
                            <button type="button" onClick={() => removeApprover(stepIdx, approverIdx)} disabled={loading} style={{ width: '32px', height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '6px', border: 'none', backgroundColor: 'transparent', cursor: 'pointer', color: '#dc2626' }}>
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          <div style={{ display: 'flex', gap: '0.75rem', paddingTop: '0.5rem', borderTop: '1px solid var(--border)' }}>
            <button type="button" onClick={onClose} disabled={loading} style={{ flex: 1, padding: '0.625rem', backgroundColor: 'var(--bg)', color: 'var(--text-secondary)', border: '1px solid var(--border-soft)', borderRadius: '0.5rem', fontSize: '0.875rem', fontWeight: 500, cursor: 'pointer', fontFamily: 'inherit' }}>
              Cancel
            </button>
            <button type="submit" disabled={loading || loadingData} style={{ flex: 1, padding: '0.625rem', backgroundColor: 'var(--text)', color: 'var(--surface)', border: 'none', borderRadius: '0.5rem', fontSize: '0.875rem', fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}>
              {loading ? <><Spin />Saving...</> : editing ? 'Save changes' : 'Create workflow'}
            </button>
          </div>
        </form>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    </div>
  )
}

const labelStyle: React.CSSProperties = { display: 'block', fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.35rem' }
const Req = () => <span style={{ color: '#ef4444' }}> *</span>
const Spin = () => <span style={{ width: '14px', height: '14px', border: '2px solid rgba(255,255,255,0.3)', borderTopColor: 'var(--surface)', borderRadius: '50%', animation: 'spin 0.7s linear infinite', display: 'inline-block' }} />
