import { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { toast } from 'react-hot-toast'
import { memoApi } from '@/api/memo.api'
import { getErrorMessage } from '@/api/client'
import { directoriesApi } from '@/api/directories.api'
import { usersApi } from '@/api/users.api'
import { workflowApi } from '@/api/workflow.api'
import { useAuthStore } from '@/store/authStore'
import type { MemoDetail, MemoCreate, MemoUpdate } from '@/types/memo.types'
import type { UserLevel } from '@/types/user.types'
import Button from '@/components/ui/Button'
import MemoForm from '@/components/memo/MemoForm'
import SignaturePicker from '@/components/memo/SignaturePicker'

export default function MemoDraftPage() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const isEdit = !!id && id !== 'new'
  const { user: currentUser } = useAuthStore()

  const [directories, setDirectories] = useState<{ id: number; name: string; category_id: number }[]>([])
  const [userLevels, setUserLevels] = useState<UserLevel[]>([])
  const [workflows, setWorkflows] = useState<Array<{ id: number; name: string }>>([])
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<number | ''>('')
  const [submitSignatureId, setSubmitSignatureId] = useState<number | null>(null)
  const [editSignatureId, setEditSignatureId] = useState<number | null>(null)
  const [memo, setMemo] = useState<MemoDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    setSubmitSignatureId(null)
    setEditSignatureId(null)
    setSelectedWorkflowId('')
    setWorkflows([])
    setMemo(null)
    setLoading(true)
  }, [id, isEdit])

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      try {
        const [dirs, levels] = await Promise.all([
          directoriesApi.list(),
          usersApi.listActiveUserLevels(),
        ])
        setDirectories(dirs.map((d) => ({ id: d.id, name: d.name, category_id: d.category_id })))
        setUserLevels(levels.filter((ul) => ul.is_active))

        if (isEdit) {
          const m = await memoApi.get(Number(id))
          setMemo(m)
          setEditSignatureId(m.author_signature_id ?? null)
          const canSubmit = !m.workflow_status || ['draft', 'returned'].includes(m.workflow_status)
          if (canSubmit) {
            const wfs = await workflowApi.list({ is_active: true })
            setWorkflows(wfs.items.map((w) => ({ id: w.id, name: w.name })))
          }
        }
      } catch {
        toast.error('Failed to load form data')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [id, isEdit])

  const handleSubmit = async (data: MemoCreate | MemoUpdate) => {
    setError('')
    setSubmitting(true)
    try {
      if (isEdit) {
        const updateData = { ...data, signature_id: editSignatureId }
        await memoApi.update(Number(id), updateData as MemoUpdate)
        toast.success('Memo updated')
        navigate('/memos')
      } else {
        const created = await memoApi.create(data as MemoCreate)
        toast.success('Memo created')
        navigate(`/memos/${created.id}`)
      }
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  const handleSubmitForApproval = async (e: React.MouseEvent) => {
    e.preventDefault()
    if (!memo || !selectedWorkflowId) return
    setError('')
    setSubmitting(true)
    try {
      await memoApi.submit(memo.id, {
        workflow_definition_id: Number(selectedWorkflowId),
        signature_id: submitSignatureId || undefined,
      })
      toast.success('Submitted for approval')
      navigate(`/memos/${memo.id}`)
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '3rem' }}>Loading...</div>
    )
  }

  const canSubmit = !!memo && (!memo.workflow_status || ['draft', 'returned'].includes(memo.workflow_status))
  const canEditSignature = isEdit && memo && ['submitted', 'pending_approval'].includes(memo.workflow_status || '')

  return (
    <div style={{ maxWidth: 800, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h1 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 600 }}>{isEdit ? 'Edit Memo' : 'New Memo'}</h1>
      </div>

      <MemoForm
        initialData={memo || {}}
        directories={directories}
        userLevels={userLevels}
        currentUser={currentUser}
        onSubmit={handleSubmit}
        onCancel={() => navigate('/memos')}
        submitting={submitting}
        isEdit={isEdit}
        existingAttachments={memo?.attachments || []}
        error={error}
        onClearError={() => setError('')}
      />

      {canEditSignature && (
        <div style={{ marginTop: '1.5rem', padding: '1rem', background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 8 }}>
          <h3 style={{ margin: '0 0 0.5rem', fontSize: '0.9rem' }}>Update Signature</h3>
          <p style={{ margin: '0 0 0.75rem', fontSize: '0.8rem', color: '#92400e' }}>
            This memo is under review. You can update your signature before approval.
          </p>
          <SignaturePicker
            key={`edit-sig-${id}`}
            selectedSignatureId={editSignatureId}
            onSelect={setEditSignatureId}
            memoAuthorSignatureId={memo?.author_signature_id}
          />
        </div>
      )}

      {isEdit && canSubmit && workflows.length > 0 && (
        <div style={{ marginTop: '1.5rem', padding: '1rem', background: '#f0f9ff', border: '1px solid #bae6fd', borderRadius: 8 }}>
          <h3 style={{ margin: '0 0 0.5rem', fontSize: '0.9rem' }}>Submit for Approval</h3>
          <p style={{ margin: '0 0 0.75rem', fontSize: '0.8rem', color: '#0369a1' }}>
            This memo is a draft. Select a workflow to route it for approval.
          </p>
          <div style={{ marginBottom: '0.75rem' }}>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 500, marginBottom: '4px', color: '#334155' }}>Workflow</label>
            <select
              value={selectedWorkflowId}
              onChange={(e) => setSelectedWorkflowId(Number(e.target.value) || '')}
              style={{ width: '100%', padding: '8px 12px', border: '1px solid #cbd5e1', borderRadius: 6, fontSize: '0.85rem' }}
            >
              <option value="">Select workflow</option>
              {workflows.map((w) => (
                <option key={w.id} value={w.id}>{w.name}</option>
              ))}
            </select>
          </div>
          <SignaturePicker key={`sig-${id || 'new'}`} selectedSignatureId={submitSignatureId} onSelect={setSubmitSignatureId} memoAuthorSignatureId={memo?.author_signature_id} />
          <div style={{ marginTop: '0.75rem' }}>
            <Button onClick={handleSubmitForApproval} disabled={submitting || !selectedWorkflowId}>
              {submitting ? 'Submitting...' : 'Submit for Approval'}
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}