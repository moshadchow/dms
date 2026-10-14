import { useState } from 'react'
import Modal from '@/components/ui/Modal'
import Button from '@/components/ui/Button'
import type { DispatchMethod } from '@/types/correspondence.types'

interface Props {
  isOpen: boolean
  onClose: () => void
  onConfirm: (data: { dispatch_method: DispatchMethod; dispatch_reference?: string; remarks?: string }) => Promise<void>
}

const METHOD_OPTIONS: { value: DispatchMethod; label: string }[] = [
  { value: 'email', label: 'Email' },
  { value: 'courier', label: 'Courier' },
  { value: 'post', label: 'Post' },
  { value: 'hand_delivery', label: 'Hand Delivery' },
  { value: 'portal', label: 'Portal' },
  { value: 'other', label: 'Other' },
]

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '8px 10px', borderRadius: '6px',
  border: '1px solid var(--border)', backgroundColor: 'var(--surface)',
  color: 'var(--text)', fontSize: '0.85rem', outline: 'none', boxSizing: 'border-box',
}

export default function CorrespondenceDispatchDialog({ isOpen, onClose, onConfirm }: Props) {
  const [method, setMethod] = useState<DispatchMethod>('email')
  const [ref, setRef] = useState('')
  const [remarks, setRemarks] = useState('')
  const [loading, setLoading] = useState(false)

  const handleConfirm = async () => {
    setLoading(true)
    try {
      await onConfirm({ dispatch_method: method, dispatch_reference: ref || undefined, remarks: remarks || undefined })
      onClose()
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Dispatch Correspondence"
      subtitle="Record the dispatch method and details"
      footer={
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={handleConfirm} loading={loading}>Confirm Dispatch</Button>
        </div>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <div>
          <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>Method *</label>
          <select value={method} onChange={(e) => setMethod(e.target.value as DispatchMethod)} style={inputStyle}>
            {METHOD_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        <div>
          <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>Dispatch Reference</label>
          <input value={ref} onChange={(e) => setRef(e.target.value)} placeholder="Tracking number, email ID, etc." style={inputStyle} />
        </div>
        <div>
          <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>Remarks</label>
          <textarea value={remarks} onChange={(e) => setRemarks(e.target.value)} rows={3} style={{ ...inputStyle, resize: 'vertical' }} />
        </div>
      </div>
    </Modal>
  )
}
