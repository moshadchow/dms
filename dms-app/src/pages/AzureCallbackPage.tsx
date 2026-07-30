import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'react-hot-toast'
import { authApi } from '@/api/auth.api'
import { useAuthStore } from '@/store/authStore'
import Spinner from '@/components/ui/Spinner'

export default function AzureCallbackPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { setTokens, setUser } = useAuthStore()
  const [error, setError] = useState('')

  useEffect(() => {
    const accessToken = searchParams.get('access_token')
    const refreshToken = searchParams.get('refresh_token')
    const authError = searchParams.get('error')

    if (authError) {
      setError(decodeURIComponent(authError))
      return
    }

    if (!accessToken || !refreshToken) {
      setError('Missing authentication tokens')
      return
    }

    const complete = async () => {
      try {
        setTokens(accessToken, refreshToken)
        const user = await authApi.me()
        setUser(user)
        toast.success(`Welcome, ${user.full_name.split(' ')[0]}!`)
        navigate('/dashboard', { replace: true })
      } catch {
        setError('Failed to load user profile')
      }
    }

    complete()
  }, [])

  if (error) {
    return (
      <div style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'var(--bg)',
        padding: '1rem',
      }}>
        <div style={{
          maxWidth: '400px',
          width: '100%',
          backgroundColor: 'var(--surface)',
          borderRadius: '1.25rem',
          boxShadow: 'var(--shadow-lg)',
          padding: '2.5rem 2rem',
          border: '1px solid var(--border)',
          textAlign: 'center',
        }}>
          <div style={{
            width: '56px',
            height: '56px',
            backgroundColor: 'var(--danger-bg)',
            borderRadius: '14px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 1rem',
          }}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--danger)" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          </div>
          <h2 style={{ fontWeight: 700, color: 'var(--text)', margin: '0 0 0.5rem' }}>
            Authentication Failed
          </h2>
          <p style={{ color: 'var(--text-tertiary)', fontSize: '0.875rem', margin: '0 0 1.5rem' }}>
            {error}
          </p>
          <button
            onClick={() => navigate('/login', { replace: true })}
            style={{
              padding: '0.75rem 1.5rem',
              backgroundColor: 'var(--text)',
              color: 'var(--surface)',
              border: 'none',
              borderRadius: '0.625rem',
              fontSize: '0.95rem',
              fontWeight: 700,
              cursor: 'pointer',
              fontFamily: 'inherit',
            }}
          >
            Back to Login
          </button>
        </div>
      </div>
    )
  }

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: 'var(--bg)',
    }}>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}>
        <Spinner size="lg" />
        <p style={{ color: 'var(--text-tertiary)', fontSize: '0.85rem' }}>Completing sign-in…</p>
      </div>
    </div>
  )
}
