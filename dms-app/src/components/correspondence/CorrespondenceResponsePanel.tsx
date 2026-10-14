import { useNavigate } from 'react-router-dom'
import type { Correspondence } from '@/types/correspondence.types'

interface Props {
  correspondence: Correspondence
}

export default function CorrespondenceResponsePanel({ correspondence }: Props) {
  const navigate = useNavigate()

  if (!correspondence.response_required && !correspondence.parent_correspondence_id) {
    return null
  }

  return (
    <div style={{
      padding: '12px', borderRadius: '8px', border: '1px solid var(--border)',
      backgroundColor: 'var(--surface)',
    }}>
      <h4 style={{ margin: '0 0 8px', fontSize: '0.85rem', color: 'var(--text)' }}>Response Information</h4>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '0.82rem' }}>
        {correspondence.response_required && (
          <>
            <div>
              <span style={{ color: 'var(--text-tertiary)' }}>Required: </span>
              <strong style={{ color: correspondence.response_received ? 'var(--success)' : 'var(--warning)' }}>
                {correspondence.response_received ? 'Yes (Received)' : 'Yes'}
              </strong>
            </div>
            {correspondence.response_deadline && (
              <div>
                <span style={{ color: 'var(--text-tertiary)' }}>Deadline: </span>
                <span style={{
                  color: new Date(correspondence.response_deadline) < new Date() && !correspondence.response_received
                    ? 'var(--danger)' : 'var(--text)',
                }}>
                  {new Date(correspondence.response_deadline).toLocaleDateString()}
                </span>
              </div>
            )}
            {correspondence.responded_at && (
              <div>
                <span style={{ color: 'var(--text-tertiary)' }}>Responded: </span>
                {new Date(correspondence.responded_at).toLocaleDateString()}
              </div>
            )}
          </>
        )}
        {correspondence.parent_correspondence_id && (
          <div>
            <span style={{ color: 'var(--text-tertiary)' }}>Response to: </span>
            <button
              onClick={() => navigate(`/correspondence/${correspondence.parent_correspondence_id}`)}
              style={{
                background: 'none', border: 'none', color: 'var(--primary)',
                fontWeight: 600, cursor: 'pointer', padding: 0, fontSize: '0.82rem',
                textDecoration: 'underline',
              }}
            >
              {correspondence.parent_reference || `#${correspondence.parent_correspondence_id}`}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
