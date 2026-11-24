import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'react-hot-toast'
import { authApi } from '@/api/auth.api'
import { apiRoot } from '@/api/base'
import { useAuthStore } from '@/store/authStore'
import { getErrorMessage } from '@/api/client'
import ThemeToggle from '@/components/ui/ThemeToggle'
import ucbLogo from '@/assets/ucb_logo.png'
import type { LoginResponse } from '@/types/auth.types'
import type { AzureProviderCompany } from '@/types/company.types'

// Light theme fallback colors (used when CSS variables aren't loaded)
const colors = {
  bg: '#f0fdfa',
  surface: '#ffffff',
  border: '#5eead4',
  text: '#134e4a',
  textSecondary: '#475569',
  textTertiary: '#94a3b8',
  dangerBg: '#fef2f2',
  danger: '#dc2626',
  primary: '#0d9488',
  primaryHover: '#0f766e',
  surface2: '#f1f5f9',
  borderSoft: '#e2e8f0',
  inputBg: '#f8fafc',
  inputBorder: '#e2e8f0',
  shadowLg: '0 20px 60px rgba(0,0,0,0.15)',
}

export default function LoginPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { setTokens, setUser, isAuthenticated } = useAuthStore()

  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [showPass, setShowPass] = useState(false)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState(() => searchParams.get('error') ?? '')
  const [azureEnabled, setAzureEnabled] = useState(false)
  const [azureCompanies, setAzureCompanies] = useState<AzureProviderCompany[]>([])
  const [selectedCompanyId, setSelectedCompanyId] = useState<number | ''>('')
  const [showCompanySelector, setShowCompanySelector] = useState(false)
  const [localSelection, setLocalSelection] = useState(false)
  const [companyOptions, setCompanyOptions] = useState<{ id: number; name: string }[]>([])

  useEffect(() => {
    fetch(`${apiRoot}/auth/azure/config`)
      .then((r) => r.json())
      .then((data) => {
        setAzureEnabled(Boolean(data.enabled))
        setAzureCompanies(data.companies || [])
      })
      .catch(() => {})
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    useAuthStore.getState().logout()
    setError('')
    if (!email.trim() || !password.trim()) { setError('Email and password are required.'); return }
    setLoading(true)
    try {
      const companies = await authApi.companiesByEmail(email.trim())
      if (companies.length > 1) {
        setCompanyOptions(companies)
        setLocalSelection(true)
        setShowCompanySelector(true)
        return
      }
      const companyId = companies.length === 1 ? companies[0].id : undefined
      const result = await authApi.login({ email: email.trim(), password, company_id: companyId })
      if (!result.access_token || !result.refresh_token) { setError('Login failed.'); return }
      setTokens(result.access_token, result.refresh_token)
      const user = await authApi.me()
      setUser(user)
      toast.success(`Welcome back, ${user.full_name.split(' ')[0]}!`)
      if (user.must_change_password) {
        navigate('/force-change-password', { replace: true })
      } else {
        navigate('/dashboard', { replace: true })
      }
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  const handleAzureLogin = () => {
    if (azureCompanies.length === 1) {
      window.location.href = `${apiRoot}/auth/azure/login?company_id=${azureCompanies[0].id}`
    } else if (azureCompanies.length > 1) {
      setShowCompanySelector(true)
    }
  }

  const handleLocalCompanySelected = async () => {
    if (!localSelection || selectedCompanyId === '') { setError('Please select a company.'); return }
    setLoading(true)
    try {
      const result = await authApi.login({ email: email.trim(), password, company_id: Number(selectedCompanyId) })
      if (!result.access_token || !result.refresh_token) { setError('Login failed.'); return }
      setTokens(result.access_token, result.refresh_token)
      const user = await authApi.me()
      setUser(user)
      toast.success(`Welcome back, ${user.full_name.split(' ')[0]}!`)
      if (user.must_change_password) {
        navigate('/force-change-password', { replace: true })
      } else {
        navigate('/dashboard', { replace: true })
      }
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  const handleCompanySelected = () => {
    if (selectedCompanyId === '') {
      setError('Please select a company.')
      return
    }
    window.location.href = `${apiRoot}/auth/azure/login?company_id=${selectedCompanyId}`
  }

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: `var(--bg, ${colors.bg})`,
      padding: '1rem',
      transition: 'background-color 200ms',
    }}>

      <div style={{ position: 'fixed', top: '1rem', right: '1rem' }}>
        <ThemeToggle />
      </div>

      <div style={{
        width: '100%',
        maxWidth: '400px',
        backgroundColor: `var(--surface, ${colors.surface})`,
        borderRadius: '1.25rem',
        boxShadow: `var(--shadow-lg, ${colors.shadowLg})`,
        padding: '2.5rem 2rem',
        border: `1px solid var(--border, ${colors.border})`,
        transition: 'background-color 200ms',
      }}>

        {/* Logo */}
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '1.75rem' }}>
          <div style={{
            backgroundColor: '#1a1a2e',
            borderRadius: '12px',
            padding: '12px 24px',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
            <img
              src={ucbLogo}
              alt="UCB Logo"
              style={{
                width: '200px',
                maxWidth: '100%',
                height: 'auto',
                objectFit: 'contain',
                display: 'block',
                userSelect: 'none',
              }}
            />
          </div>
        </div>

        {/* Title */}
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: `var(--text, ${colors.text})`, margin: 0 }}>Document Management System</h1>
          <p style={{ color: `var(--text-tertiary, ${colors.textTertiary})`, fontSize: '0.875rem', marginTop: '0.5rem' }}>Sign in to access your documents</p>
        </div>

        {/* Error */}
        {error && (
          <div role="alert" style={{
            padding: '0.75rem 1rem',
            backgroundColor: `var(--danger-bg, ${colors.dangerBg})`,
            border: `1px solid var(--danger, ${colors.danger})`,
            borderRadius: '0.625rem',
            color: `var(--danger, ${colors.danger})`,
            fontSize: '0.85rem',
            marginBottom: '1rem'
          }}>
            {error}
          </div>
        )}

        {/* Company selector modal for Azure AD / duplicate email */}
        {showCompanySelector && (localSelection || azureCompanies.length > 0) ? (
          <div>
            <h2 style={{ fontSize: '1rem', fontWeight: 600, color: `var(--text, ${colors.text})`, marginBottom: '0.75rem' }}>
              Select your company
            </h2>
            <p style={{ color: `var(--text-tertiary, ${colors.textTertiary})`, fontSize: '0.82rem', marginBottom: '1rem' }}>
              Choose the company you want to sign in with.
            </p>
            <div style={{ marginBottom: '1rem' }}>
              <select
                className="input"
                value={selectedCompanyId}
                onChange={(e) => setSelectedCompanyId(e.target.value ? Number(e.target.value) : '')}
                style={{ width: '100%', fontSize: '0.875rem' }}
              >
                <option value="">-- Select company --</option>
                {(localSelection ? companyOptions : azureCompanies).map((c: any) => (
                  <option key={c.id} value={c.id}>{c.name ?? c.full_name ?? c.short_name}</option>
                ))}
              </select>
            </div>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button
                onClick={localSelection ? handleLocalCompanySelected : handleCompanySelected}
                className="btn btn-primary"
                style={{ flex: 1, padding: '0.75rem', fontSize: '0.95rem', fontWeight: 700 }}
              >
                {localSelection ? 'Continue' : 'Continue with Microsoft'}
              </button>
              <button
                onClick={() => { setShowCompanySelector(false); setSelectedCompanyId('') }}
                className="btn btn-secondary"
                style={{ padding: '0.75rem 1rem', fontSize: '0.875rem' }}
              >
                Back
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            {/* Email */}
            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, color: `var(--text-secondary, ${colors.textSecondary})`, marginBottom: '0.4rem' }}>Email</label>
              <input type="text" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" autoComplete="email" disabled={loading} className="input" />
            </div>

            {/* Password */}
            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, color: `var(--text-secondary, ${colors.textSecondary})`, marginBottom: '0.4rem' }}>Password</label>
              <div style={{ position: 'relative' }}>
                <input type={showPass ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" autoComplete="current-password" disabled={loading} className="input" style={{ paddingRight: '2.5rem' }} />
                <button type="button" onClick={() => setShowPass(!showPass)} aria-label={showPass ? 'Hide password' : 'Show password'} style={{ position: 'absolute', right: '0.75rem', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: `var(--text-tertiary, ${colors.textTertiary})`, padding: 0, lineHeight: 1 }}>
                  {showPass
                    ? <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
                    : <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                  }
                </button>
              </div>
            </div>

            {/* Submit */}
            <button type="submit" disabled={loading} aria-busy={loading} className="btn btn-primary" style={{ width: '100%', padding: '0.75rem', fontSize: '0.95rem', fontWeight: 700 }}>
              {loading ? (
                <><span style={{ width: '16px', height: '16px', border: '2px solid rgba(255,255,255,0.3)', borderTopColor: 'currentColor', borderRadius: '50%', display: 'inline-block', animation: 'spin 0.7s linear infinite' }} />Signing in…</>
              ) : 'Sign In'}
            </button>
          </form>
        )}

        {/* Azure AD SSO */}
        {azureEnabled && !showCompanySelector && (
          <>
            <div style={{ display: 'flex', alignItems: 'center', margin: '1.5rem 0', gap: '0.75rem' }}>
              <div style={{ flex: 1, height: '1px', backgroundColor: `var(--border, ${colors.border})` }} />
              <span style={{ fontSize: '0.8rem', color: `var(--text-tertiary, ${colors.textTertiary})`, whiteSpace: 'nowrap' }}>or</span>
              <div style={{ flex: 1, height: '1px', backgroundColor: `var(--border, ${colors.border})` }} />
            </div>
            <button
              onClick={handleAzureLogin}
              className="btn btn-secondary"
              style={{
                width: '100%',
                padding: '0.75rem',
                fontSize: '0.95rem',
                fontWeight: 600,
                display: 'flex',
                justifyContent: 'center',
                gap: '0.75rem',
              }}
            >
              <svg width="20" height="20" viewBox="0 0 23 23" xmlns="http://www.w3.org/2000/svg">
                <rect x="1" y="1" width="10" height="10" fill="#f25022" />
                <rect x="12" y="1" width="10" height="10" fill="#7fba00" />
                <rect x="1" y="12" width="10" height="10" fill="#00a4ef" />
                <rect x="12" y="12" width="10" height="10" fill="#ffb900" />
              </svg>
              Sign in with Microsoft
            </button>
          </>
        )}

        <p style={{ textAlign: 'center', fontSize: '0.8rem', color: `var(--text-tertiary, ${colors.textTertiary})`, marginTop: '1.5rem' }}>
          Don't have an account? <span style={{ color: `var(--text, ${colors.text})`, fontWeight: 600 }}>Contact administrator</span>
        </p>
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); }`}</style>
    </div>
  )
}