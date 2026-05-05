import { usePermissions } from '@/hooks/usePermissions'
import type { PermissionAction } from '@/types/user.types'

interface Props {
  action?:    PermissionAction   // guard by a single permission action
  adminOnly?: boolean            // guard by admin role
  children:   React.ReactNode
  fallback?:  React.ReactNode    // render this when access is denied (default: null)
}

/**
 * PermissionGate
 *
 * Renders children only when the current user has the required
 * permission or role. Use this to conditionally show/hide UI
 * elements without scattering hasPermission() checks everywhere.
 *
 * Examples:
 *   <PermissionGate action="create">
 *     <UploadButton />
 *   </PermissionGate>
 *
 *   <PermissionGate adminOnly>
 *     <AdminLink />
 *   </PermissionGate>
 *
 *   <PermissionGate action="delete" fallback={<p>No access</p>}>
 *     <DeleteButton />
 *   </PermissionGate>
 */
export default function PermissionGate({ action, adminOnly, children, fallback = null }: Props) {
  const { isAdmin, check } = usePermissions()

  if (adminOnly && !isAdmin) return <>{fallback}</>
  if (action && !check(action)) return <>{fallback}</>

  return <>{children}</>
}
