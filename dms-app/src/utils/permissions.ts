import type { RoleName, PermissionAction } from '@/types/user.types'

// Default permission matrix — mirrors backend seed data
export const ROLE_PERMISSIONS: Record<RoleName, PermissionAction[]> = {
  admin:   ['view', 'download', 'create', 'update', 'delete'],
  maker:   ['view', 'download', 'create', 'update'],
  checker: ['view', 'download', 'update'],
  auditor: ['view', 'download'],
}

export const ROLE_LABELS: Record<RoleName, string> = {
  admin:   'Admin',
  maker:   'Maker',
  checker: 'Checker',
  auditor: 'Auditor',
}

export const ROLE_COLORS: Record<RoleName, string> = {
  admin:   'bg-purple-100 text-purple-800',
  maker:   'bg-blue-100 text-blue-800',
  checker: 'bg-amber-100 text-amber-800',
  auditor: 'bg-green-100 text-green-800',
}
