import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import toast from 'react-hot-toast'
import { correspondenceApi } from '@/api/correspondence.api'
import CorrespondenceForm from '@/components/correspondence/CorrespondenceForm'
import type { CorrespondenceCreate, CorrespondenceDirection } from '@/types/correspondence.types'
import { getErrorMessage } from '@/api/client'

export default function CorrespondenceCreatePage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [loading, setLoading] = useState(false)
  const initialDirection = (searchParams.get('direction') as CorrespondenceDirection) || undefined

  const handleSubmit = async (data: CorrespondenceCreate, file?: File | null) => {
    setLoading(true)
    try {
      const result = await correspondenceApi.create(data)
      if (file) {
        try {
          const attachmentType = data.direction === 'inbound' ? 'original' : 'supporting'
          await correspondenceApi.addAttachment(result.id, file, attachmentType)
        } catch (uploadErr) {
          toast.error(`Correspondence created but file upload failed: ${getErrorMessage(uploadErr)}`)
        }
      }
      toast.success('Correspondence created')
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
        New Correspondence
      </h1>
      <div style={{ backgroundColor: 'var(--surface)', borderRadius: '8px', border: '1px solid var(--border)', padding: '1.5rem' }}>
        <CorrespondenceForm
          initialDirection={initialDirection}
          onSubmit={handleSubmit}
          onCancel={() => navigate('/correspondence')}
          loading={loading}
        />
      </div>
    </div>
  )
}
