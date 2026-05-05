import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User, PermissionAction } from '@/types/user.types'

interface AuthState {
  user: User | null
  accessToken: string | null
  refreshToken: string | null

  setTokens: (access: string, refresh: string) => void
  setUser: (user: User) => void
  logout: () => void

  isAuthenticated: () => boolean
  isAdmin: () => boolean
  hasPermission: (action: PermissionAction) => boolean
  hasRole: (roleName: string) => boolean
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,

      setTokens: (access, refresh) => {
        localStorage.setItem('access_token', access)
        localStorage.setItem('refresh_token', refresh)
        set({ accessToken: access, refreshToken: refresh })
      },

      setUser: (user) => set({ user }),

      logout: () => {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        set({ user: null, accessToken: null, refreshToken: null })
      },

      isAuthenticated: () => Boolean(get().accessToken && get().user),

      isAdmin: () =>
        get().user?.roles.some((r) => r.name === 'admin') ?? false,

      hasPermission: (action) => {
        const { user } = get()
        if (!user) return false
        if (user.roles.some((r) => r.name === 'admin')) return true
        return user.roles.some((role) =>
          role.permissions.some((p) => p.action === action)
        )
      },

      hasRole: (roleName) =>
        get().user?.roles.some((r) => r.name === roleName) ?? false,
    }),
    {
      name: 'dms-auth',
      // Only persist tokens — user is re-fetched on page load via ProtectedRoute
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
      }),
    }
  )
)
