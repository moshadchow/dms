import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'react-hot-toast'
import { Lock, Eye, EyeOff } from 'lucide-react'
import { authApi } from '@/api/auth.api'
import { getErrorMessage } from '@/api/client'
import { useAuthStore } from '@/store/authStore'

export default function ForceChangePasswordPage() {
  const navigate = useNavigate()
  const { setUser } = useAuthStore()
  const [newPassword, setNewPassword]         = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showNew, setShowNew]                 = useState(false)
  const [showConfirm, setShowConfirm]         = useState(false)
  const [loading, setLoading]                 = useState(false)
  const [error, setError]                     = useState('')

  const validate = (): string => {
    if (!newPassword) return 'New password is required.'
    if (newPassword.length < 8) return 'New password must be at least 8 characters.'
    if (!/[A-Z]/.test(newPassword)) return 'New password must contain at least one uppercase letter.'
    if (!/[0-9]/.test(newPassword)) return 'New password must contain at least one digit.'
    if (newPassword !== confirmPassword) return 'Passwords do not match.'
    return ''
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const validationError = validate()
    if (validationError) { setError(validationError); return }

    setLoading(true)
    setError('')
    try {
      await authApi.changePassword({ current_password: '', new_password: newPassword })
      const user = await authApi.me()
      setUser(user)
      toast.success('Password updated successfully')
      navigate('/dashboard', { replace: true })
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: 'var(--bg)', padding: '1rem' }}>
      <div style={{
        width: '100%', maxWidth: '420px',
        backgroundColor: 'var(--surface)',
        borderRadius: '16px',
        boxShadow: '0 20px 60px rgba(0,0,0,0.15)',
        padding: '2.5rem 2rem 2rem',
        border: '1px solid var(--border)',
      }}>

        {/* Icon */}
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '1.25rem' }}>
          <div style={{ width: '64px', height: '64px', borderRadius: '50%', backgroundColor: '#FEF3C7', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Lock size={28} color="#D97706" strokeWidth={2} />
          </div>
        </div>

        {/* Title + subtitle */}
        <h2 style={{ margin: 0, textAlign: 'center', fontSize: '1.375rem', fontWeight: 700, color: 'var(--text)' }}>
          Change Your Password
        </h2>
        <p style={{ margin: '0.5rem 0 1.75rem', textAlign: 'center', fontSize: '0.875rem', color: 'var(--text-tertiary)', lineHeight: 1.5 }}>
          Your password has been reset by an administrator. Please choose a new password to continue.
        </p>

        {/* Error */}
        {error && (
          <div style={{ marginBottom: '1rem', padding: '0.75rem 1rem', borderRadius: '10px', backgroundColor: '#FEF2F2', border: '1px solid #FECACA', color: '#DC2626', fontSize: '0.85rem' }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.125rem' }}>

          {/* New Password */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
            <label style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-secondary)' }}>New Password</label>
            <div style={{ position: 'relative' }}>
              <input
                type={showNew ? 'text' : 'password'}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Enter new password"
                disabled={loading}
                style={inputStyle}
              />
              <button type="button" onClick={() => setShowNew(!showNew)} style={eyeBtn}>
                {showNew ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>

          {/* Confirm New Password */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
            <label style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Confirm New Password</label>
            <div style={{ position: 'relative' }}>
              <input
                type={showConfirm ? 'text' : 'password'}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Confirm new password"
                disabled={loading}
                style={inputStyle}
              />
              <button type="button" onClick={() => setShowConfirm(!showConfirm)} style={eyeBtn}>
                {showConfirm ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>

          {/* Password rules */}
          <div style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)', lineHeight: 1.5 }}>
            <p style={{ margin: '0 0 0.25rem' }}>Password must contain:</p>
            <ul style={{ margin: 0, paddingLeft: '1.25rem' }}>
              <li>At least 8 characters</li>
              <li>At least one uppercase letter</li>
              <li>At least one digit</li>
            </ul>
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={loading}
            style={{
              marginTop: '0.25rem',
              width: '100%',
              padding: '0.8rem',
              borderRadius: '10px',
              border: 'none',
              backgroundColor: loading ? 'var(--text-tertiary)' : 'var(--text)',
              color: 'var(--surface)',
              fontSize: '0.95rem',
              fontWeight: 600,
              cursor: loading ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.5rem',
              fontFamily: 'inherit',
              transition: 'background-color 150ms',
            }}
          >
            {loading
              ? <><span style={{ width: '16px', height: '16px', border: '2px solid rgba(255,255,255,0.3)', borderTopColor: '#fff', borderRadius: '50%', animation: 'spin 0.7s linear infinite', display: 'inline-block' }} /> Updating…</>
              : 'Update Password'
            }
          </button>
        </form>
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '0.7rem 2.75rem 0.7rem 0.875rem',
  borderRadius: '10px',
  border: '1px solid var(--border)',
  backgroundColor: 'var(--bg)',
  fontSize: '0.9rem',
  color: 'var(--text)',
  outline: 'none',
  boxSizing: 'border-box',
  fontFamily: 'inherit',
}

const eyeBtn: React.CSSProperties = {
  position: 'absolute',
  right: '0.75rem',
  top: '50%',
  transform: 'translateY(-50%)',
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  color: 'var(--text-tertiary)',
  display: 'flex',
  alignItems: 'center',
  padding: 0,
}
