import { useAuthStore } from '@/store/authStore'
import type { PermissionAction } from '@/types/user.types'

export function usePermissions() {
  const hasPermission = useAuthStore((s) => s.hasPermission)
  const isAdmin = useAuthStore((s) => s.isAdmin)

  return {
    canView:     hasPermission('view'),
    canDownload: hasPermission('download'),
    canCreate:   hasPermission('create'),
    canUpdate:   hasPermission('update'),
    canDelete:   hasPermission('delete'),
    isAdmin:     isAdmin(),
    check: (action: PermissionAction) => hasPermission(action),
  }
}
