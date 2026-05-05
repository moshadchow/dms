import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'react-hot-toast'
import { authApi } from '@/api/auth.api'
import { useAuthStore } from '@/store/authStore'
import { getErrorMessage } from '@/api/client'
import ThemeToggle from '@/components/ui/ThemeToggle'

export default function LoginPage() {
  const navigate = useNavigate()
  const { setTokens, setUser, isAuthenticated } = useAuthStore()

  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [showPass, setShowPass] = useState(false)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState('')

  useEffect(() => {
    if (isAuthenticated()) navigate('/dashboard', { replace: true })
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (!email.trim() || !password.trim()) { setError('Email and password are required.'); return }
    setLoading(true)
    try {
      const tokens = await authApi.login({ email: email.trim(), password })
      setTokens(tokens.access_token, tokens.refresh_token)
      const user = await authApi.me()
      setUser(user)
      toast.success(`Welcome back, ${user.full_name.split(' ')[0]}!`)
      navigate('/dashboard', { replace: true })
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: 'var(--bg)', padding: '1rem', transition: 'background-color 200ms' }}>

      {/* Theme toggle — top right */}
      <div style={{ position: 'fixed', top: '1rem', right: '1rem' }}>
        <ThemeToggle />
      </div>

      <div style={{
        width: '100%', maxWidth: '400px',
        backgroundColor: 'var(--surface)',
        borderRadius: '1.25rem',
        boxShadow: 'var(--shadow-lg)',
        padding: '2.5rem 2rem',
        border: '1px solid var(--border)',
        transition: 'background-color 200ms',
      }}>

        {/* Icon */}
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '1.5rem' }}>
          <div style={{ width: '56px', height: '56px', backgroundColor: 'var(--text)', borderRadius: '14px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--surface)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
              <line x1="16" y1="13" x2="8" y2="13"/>
              <line x1="16" y1="17" x2="8" y2="17"/>
            </svg>
          </div>
        </div>

        {/* Title */}
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--text)', margin: 0 }}>Document Management System</h1>
          <p style={{ color: 'var(--text-tertiary)', fontSize: '0.875rem', marginTop: '0.5rem' }}>Sign in to access your documents</p>
        </div>

        {/* Error */}
        {error && (
          <div style={{ padding: '0.75rem 1rem', backgroundColor: 'var(--danger-bg)', border: '1px solid var(--danger)', borderRadius: '0.625rem', color: 'var(--danger)', fontSize: '0.85rem', marginBottom: '1rem' }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          {/* Email */}
          <div style={{ marginBottom: '1rem' }}>
            <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>Email</label>
            <input type="text" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" autoComplete="email" disabled={loading} className="input" />
          </div>

          {/* Password */}
          <div style={{ marginBottom: '1.5rem' }}>
            <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>Password</label>
            <div style={{ position: 'relative' }}>
              <input type={showPass ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" autoComplete="current-password" disabled={loading} className="input" style={{ paddingRight: '2.5rem' }} />
              <button type="button" onClick={() => setShowPass(!showPass)} style={{ position: 'absolute', right: '0.75rem', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-tertiary)', padding: 0, lineHeight: 1 }}>
                {showPass
                  ? <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
                  : <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                }
              </button>
            </div>
          </div>

          {/* Submit */}
          <button type="submit" disabled={loading} style={{ width: '100%', padding: '0.75rem', backgroundColor: 'var(--text)', color: 'var(--surface)', border: 'none', borderRadius: '0.625rem', fontSize: '0.95rem', fontWeight: 700, cursor: loading ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', transition: 'opacity 150ms', opacity: loading ? 0.7 : 1, fontFamily: 'inherit' }}>
            {loading ? (
              <><span style={{ width: '16px', height: '16px', border: '2px solid rgba(255,255,255,0.3)', borderTopColor: 'currentColor', borderRadius: '50%', display: 'inline-block', animation: 'spin 0.7s linear infinite' }} />Signing in…</>
            ) : 'Sign In'}
          </button>
        </form>

        <p style={{ textAlign: 'center', fontSize: '0.8rem', color: 'var(--text-tertiary)', marginTop: '1.5rem' }}>
          Don't have an account? <span style={{ color: 'var(--text)', fontWeight: 600 }}>Contact administrator</span>
        </p>
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
