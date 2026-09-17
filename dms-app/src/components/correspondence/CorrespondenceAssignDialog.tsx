import { useState, useEffect } from 'react'
import Modal from '@/components/ui/Modal'
import Button from '@/components/ui/Button'
import { usersApi } from '@/api/users.api'
import type { User } from '@/types/user.types'

interface Props {
  isOpen: boolean
  onClose: () => void
  onConfirm: (data: { to_user_id: number; remarks?: string }) => Promise<void>
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '8px 10px', borderRadius: '6px',
  border: '1px solid var(--border)', backgroundColor: 'var(--surface)',
  color: 'var(--text)', fontSize: '0.85rem', outline: 'none', boxSizing: 'border-box',
}

export default function CorrespondenceAssignDialog({ isOpen, onClose, onConfirm }: Props) {
  const [users, setUsers] = useState<User[]>([])
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null)
  const [remarks, setRemarks] = useState('')
  const [loading, setLoading] = useState(false)
  const [fetching, setFetching] = useState(false)

  useEffect(() => {
    if (isOpen) {
      setFetching(true)
      usersApi.list({ limit: 200 }).then(res => {
        setUsers(res.items)
      }).catch(() => {}).finally(() => setFetching(false))
    }
  }, [isOpen])

  const handleConfirm = async () => {
    if (!selectedUserId) return
    setLoading(true)
    try {
      await onConfirm({ to_user_id: selectedUserId, remarks: remarks || undefined })
      onClose()
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Assign / Forward"
      subtitle="Select a user to assign or forward this correspondence"
      footer={
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={handleConfirm} loading={loading} disabled={!selectedUserId}>Confirm</Button>
        </div>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <div>
          <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>Select User *</label>
          {fetching ? (
            <div style={{ padding: '8px', color: 'var(--text-tertiary)', fontSize: '0.82rem' }}>Loading users...</div>
          ) : (
            <select value={selectedUserId ?? ''} onChange={(e) => setSelectedUserId(Number(e.target.value) || null)} style={inputStyle}>
              <option value="">— Select a user —</option>
              {users.map(u => (
                <option key={u.id} value={u.id}>{u.full_name} ({u.email})</option>
              ))}
            </select>
          )}
        </div>
        <div>
          <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>Remarks</label>
          <textarea value={remarks} onChange={(e) => setRemarks(e.target.value)} rows={3} style={{ ...inputStyle, resize: 'vertical' }} placeholder="Optional notes..." />
        </div>
      </div>
    </Modal>
  )
}
