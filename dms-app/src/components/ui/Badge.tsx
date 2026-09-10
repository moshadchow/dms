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
  admin:     { bg: 'var(--primary-soft)', color: 'var(--primary)', label: 'Admin' },
  maker:     { bg: 'var(--info-bg)', color: 'var(--info)', label: 'Maker' },
  checker:   { bg: 'var(--accent-soft)', color: 'var(--accent)', label: 'Checker' },
  auditor:   { bg: 'var(--success-bg)', color: 'var(--success)', label: 'Auditor' },
  superadmin: { bg: '#fef3c7', color: '#92400e', label: 'Super Admin' },
}

const STATUS_STYLES: Record<DocumentStatus, { bg: string; color: string; label: string }> = {
  active:   { bg: 'var(--success-bg)', color: 'var(--success)', label: 'Active' },
  archived: { bg: 'var(--warning-bg)', color: 'var(--warning)', label: 'Archived' },
  deleted:  { bg: 'var(--danger-bg)', color: 'var(--danger)', label: 'Deleted' },
}

export default function Badge({ variant = 'custom', role, status, label, color = 'var(--text-secondary)', bg = 'var(--surface-2)' }: Props) {
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
