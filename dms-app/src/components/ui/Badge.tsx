import type { RoleName } from '@/types/user.types'
import type { DocumentStatus } from '@/types/document.types'

type BadgeVariant = 'role' | 'status' | 'filetype' | 'custom'

interface Props {
  variant?: BadgeVariant
  role?:    RoleName
  status?:  DocumentStatus
  label?:   string
  color?:   string
  bg?:      string
}

const ROLE_STYLES: Record<RoleName, { bg: string; color: string; label: string }> = {
  admin:   { bg: '#f3e8ff', color: '#7c3aed', label: 'Admin' },
  maker:   { bg: '#dbeafe', color: '#1d4ed8', label: 'Maker' },
  checker: { bg: '#ffedd5', color: '#c2410c', label: 'Checker' },
  auditor: { bg: '#dcfce7', color: '#15803d', label: 'Auditor' },
}

const STATUS_STYLES: Record<DocumentStatus, { bg: string; color: string; label: string }> = {
  active:   { bg: '#f0fdf4', color: '#16a34a', label: 'Active' },
  archived: { bg: '#fefce8', color: '#ca8a04', label: 'Archived' },
  deleted:  { bg: '#fef2f2', color: '#dc2626', label: 'Deleted' },
}

export default function Badge({ variant = 'custom', role, status, label, color = '#475569', bg = '#f1f5f9' }: Props) {
  let resolvedBg    = bg
  let resolvedColor = color
  let resolvedLabel = label ?? ''

  if (variant === 'role' && role) {
    const s = ROLE_STYLES[role]
    resolvedBg    = s.bg
    resolvedColor = s.color
    resolvedLabel = s.label
  } else if (variant === 'status' && status) {
    const s = STATUS_STYLES[status]
    resolvedBg    = s.bg
    resolvedColor = s.color
    resolvedLabel = s.label
  }

  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center',
      padding: '2px 8px', borderRadius: '999px',
      fontSize: '0.72rem', fontWeight: 600,
      backgroundColor: resolvedBg, color: resolvedColor,
      whiteSpace: 'nowrap',
    }}>
      {resolvedLabel}
    </span>
  )
}
