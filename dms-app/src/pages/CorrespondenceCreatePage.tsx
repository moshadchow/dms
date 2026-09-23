import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import toast from 'react-hot-toast'
import { correspondenceApi } from '@/api/correspondence.api'
import CorrespondenceForm from '@/components/correspondence/CorrespondenceForm'
import type { CorrespondenceCreate, CorrespondenceDirection, CorrespondenceDetail } from '@/types/correspondence.types'
import { getErrorMessage } from '@/api/client'

export default function CorrespondenceCreatePage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const parentId = searchParams.get('parent_id') ? Number(searchParams.get('parent_id')) : null
  const [loading, setLoading] = useState(false)
  const [parent, setParent] = useState<CorrespondenceDetail | null>(null)
  const [parentLoading, setParentLoading] = useState<boolean>(() => !!parentId)
  const initialDirection = (searchParams.get('direction') as CorrespondenceDirection) || undefined

  useEffect(() => {
    if (!parentId) return
    let active = true
    correspondenceApi.get(parentId)
      .then(p => { if (active) setParent(p) })
      .catch(() => { if (active) toast.error('Unable to load the correspondence being replied to') })
      .finally(() => { if (active) setParentLoading(false) })
    return () => { active = false }
  }, [parentId])

  const handleSubmit = async (data: CorrespondenceCreate, file?: File | null) => {
    setLoading(true)
    try {
      const result = parentId
        ? await correspondenceApi.createReply(parentId, data)
        : await correspondenceApi.create(data)
      if (file) {
        try {
          const attachmentType = data.direction === 'inbound' ? 'original' : 'supporting'
          await correspondenceApi.addAttachment(result.id, file, attachmentType)
        } catch (uploadErr) {
          toast.error(`Correspondence created but file upload failed: ${getErrorMessage(uploadErr)}`)
        }
      }
      toast.success(parentId ? 'Reply created' : 'Correspondence created')
      navigate(`/correspondence/${result.id}`)
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ padding: '1.5rem', maxWidth: '900px', margin: '0 auto' }}>
      <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--text)', margin: '0 0 1.5rem' }}>
        {parentId ? 'New Reply' : 'New Correspondence'}
      </h1>
      {parentLoading ? (
        <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-tertiary)' }}>Loading parent correspondence...</div>
      ) : (
        <div style={{ backgroundColor: 'var(--surface)', borderRadius: '8px', border: '1px solid var(--border)', padding: '1.5rem' }}>
          <CorrespondenceForm
            initialDirection={initialDirection}
            parent={parentId && !parent ? null : parent}
            onSubmit={handleSubmit}
            onCancel={() => navigate(parentId ? `/correspondence/${parentId}` : '/correspondence')}
            loading={loading}
          />
        </div>
      )}
    </div>
  )
}