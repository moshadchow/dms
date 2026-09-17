import { useState } from 'react'
import type { CorrespondenceDirection, CorrespondencePriority, CorrespondenceStatus } from '@/types/correspondence.types'
import Button from '@/components/ui/Button'

interface Props {
  direction: CorrespondenceDirection | ''
  onDirectionChange: (v: CorrespondenceDirection | '') => void
  priority: CorrespondencePriority | ''
  onPriorityChange: (v: CorrespondencePriority | '') => void
  status: CorrespondenceStatus | ''
  onStatusChange: (v: CorrespondenceStatus | '') => void
  search: string
  onSearchChange: (v: string) => void
  responseRequired: boolean | null
  onResponseRequiredChange: (v: boolean | null) => void
  onReset: () => void
}

const DIRECTION_OPTIONS: { value: CorrespondenceDirection | ''; label: string }[] = [
  { value: '', label: 'All Directions' },
  { value: 'inbound', label: 'Incoming' },
  { value: 'outbound', label: 'Outgoing' },
  { value: 'internal', label: 'Internal' },
]

const PRIORITY_OPTIONS: { value: CorrespondencePriority | ''; label: string }[] = [
  { value: '', label: 'All Priorities' },
  { value: 'low', label: 'Low' },
  { value: 'normal', label: 'Normal' },
  { value: 'high', label: 'High' },
  { value: 'urgent', label: 'Urgent' },
]

const STATUS_OPTIONS: { value: CorrespondenceStatus | ''; label: string }[] = [
  { value: '', label: 'All Statuses' },
  { value: 'draft', label: 'Draft' },
  { value: 'received', label: 'Received' },
  { value: 'submitted', label: 'Submitted' },
  { value: 'pending_approval', label: 'Pending Approval' },
  { value: 'approved', label: 'Approved' },
  { value: 'dispatched', label: 'Dispatched' },
  { value: 'completed', label: 'Completed' },
  { value: 'cancelled', label: 'Cancelled' },
  { value: 'archived', label: 'Archived' },
]

const selectStyle: React.CSSProperties = {
  padding: '6px 10px', borderRadius: '6px', border: '1px solid var(--border)',
  backgroundColor: 'var(--surface)', color: 'var(--text)', fontSize: '0.82rem',
  outline: 'none', minWidth: '130px',
}

export default function CorrespondenceFilters({
  direction, onDirectionChange,
  priority, onPriorityChange,
  status, onStatusChange,
  search, onSearchChange,
  responseRequired, onResponseRequiredChange,
  onReset,
}: Props) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center' }}>
      <input
        type="text"
        placeholder="Search reference, subject, sender..."
        value={search}
        onChange={(e) => onSearchChange(e.target.value)}
        style={{
          flex: '1 1 200px', padding: '6px 10px', borderRadius: '6px',
          border: '1px solid var(--border)', backgroundColor: 'var(--surface)',
          color: 'var(--text)', fontSize: '0.82rem', outline: 'none',
        }}
      />
      <select value={direction} onChange={(e) => onDirectionChange(e.target.value as CorrespondenceDirection | '')} style={selectStyle}>
        {DIRECTION_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
      <select value={priority} onChange={(e) => onPriorityChange(e.target.value as CorrespondencePriority | '')} style={selectStyle}>
        {PRIORITY_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
      <select value={status} onChange={(e) => onStatusChange(e.target.value as CorrespondenceStatus | '')} style={selectStyle}>
        {STATUS_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
      <select
        value={responseRequired === null ? '' : String(responseRequired)}
        onChange={(e) => onResponseRequiredChange(e.target.value === '' ? null : e.target.value === 'true')}
        style={selectStyle}
      >
        <option value="">All Response</option>
        <option value="true">Response Required</option>
        <option value="false">No Response Needed</option>
      </select>
      <Button variant="ghost" size="sm" onClick={onReset}>Reset</Button>
    </div>
  )
}
