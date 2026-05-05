import { ROLE_LABELS } from '@/utils/permissions'
import type { Role, RoleName, PermissionAction } from '@/types/user.types'

interface Props { roles: Role[] }

const ACTIONS: PermissionAction[] = ['view', 'download', 'create', 'update', 'delete']

const ACTION_LABELS: Record<PermissionAction, string> = {
  view:     'View',
  download: 'Download',
  create:   'Create',
  update:   'Update',
  delete:   'Delete',
}

const ROLE_ORDER: RoleName[] = ['admin', 'maker', 'checker', 'auditor']

export default function PermissionMatrix({ roles }: Props) {
  // Sort roles by defined order
  const sorted = [...roles].sort(
    (a, b) => ROLE_ORDER.indexOf(a.name as RoleName) - ROLE_ORDER.indexOf(b.name as RoleName)
  )

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid #f1f5f9' }}>
            <th style={{ padding: '0.75rem 1rem', textAlign: 'left', fontSize: '0.72rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Role
            </th>
            {ACTIONS.map((action) => (
              <th key={action} style={{ padding: '0.75rem 1rem', textAlign: 'center', fontSize: '0.72rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                {ACTION_LABELS[action]}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((role, i) => {
            const perms = new Set(role.permissions.map((p) => p.action))
            return (
              <tr key={role.id} style={{ borderBottom: i < sorted.length - 1 ? '1px solid #f8fafc' : 'none' }}>
                <td style={{ padding: '0.875rem 1rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <RoleDot name={role.name as RoleName} />
                    <span style={{ fontWeight: 600, color: '#1e293b' }}>
                      {ROLE_LABELS[role.name as RoleName] ?? role.name}
                    </span>
                  </div>
                </td>
                {ACTIONS.map((action) => (
                  <td key={action} style={{ padding: '0.875rem 1rem', textAlign: 'center' }}>
                    {perms.has(action) ? (
                      <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: '24px', height: '24px', borderRadius: '50%', backgroundColor: '#f0fdf4' }}>
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2.5">
                          <polyline points="20 6 9 17 4 12"/>
                        </svg>
                      </span>
                    ) : (
                      <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: '24px', height: '24px', borderRadius: '50%', backgroundColor: '#f8fafc' }}>
                        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#e2e8f0" strokeWidth="2.5">
                          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                        </svg>
                      </span>
                    )}
                  </td>
                ))}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function RoleDot({ name }: { name: RoleName }) {
  const colors: Record<RoleName, string> = {
    admin:   '#7c3aed',
    maker:   '#2563eb',
    checker: '#ea580c',
    auditor: '#16a34a',
  }
  return (
    <span style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: colors[name] ?? '#94a3b8', display: 'inline-block', flexShrink: 0 }} />
  )
}
