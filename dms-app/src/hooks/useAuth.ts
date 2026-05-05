import { useAuthStore } from '@/store/authStore'

export function useAuth() {
  const store = useAuthStore()
  return {
    user: store.user,
    isAuthenticated: store.isAuthenticated(),
    isAdmin: store.isAdmin(),
    hasPermission: store.hasPermission,
    hasRole: store.hasRole,
    logout: store.logout,
  }
}
