import { useEffect, useState } from 'react'
import { Navigate, Outlet } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { authApi } from '@/api/auth.api'
import Spinner from '@/components/ui/Spinner'

export default function ProtectedRoute() {
  const { accessToken, refreshToken, setTokens, setUser, logout } = useAuthStore()
  const [checking, setChecking] = useState(true)

  useEffect(() => {
    const verify = async () => {
      // No token at all — go to login
      if (!accessToken) {
        setChecking(false)
        return
      }

      try {
        // Verify token is still valid by fetching current user
        const user = await authApi.me()
        setUser(user)
      } catch {
        // Access token expired — try refresh
        if (refreshToken) {
          try {
            const tokens = await authApi.refresh(refreshToken)
            setTokens(tokens.access_token, tokens.refresh_token)
            const user = await authApi.me()
            setUser(user)
          } catch {
            // Refresh also failed — clear everything
            logout()
          }
        } else {
          logout()
        }
      } finally {
        setChecking(false)
      }
    }

    verify()
  }, [])

  if (checking) {
    return (
      <div className="flex h-screen items-center justify-center bg-surface-50">
        <div className="flex flex-col items-center gap-3">
          <Spinner size="lg" />
          <p className="text-sm text-slate-400">Verifying session…</p>
        </div>
      </div>
    )
  }

  if (!accessToken) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}
