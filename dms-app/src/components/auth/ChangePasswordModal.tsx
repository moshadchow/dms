import { useState } from 'react'
import { toast } from 'react-hot-toast'
import { Lock, Eye, EyeOff } from 'lucide-react'
import { authApi } from '@/api/auth.api'
import { getErrorMessage } from '@/api/client'

interface Props {
  isOpen: boolean
  onClose: () => void
}

export default function ChangePasswordModal({ isOpen, onClose }: Props) {
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword]         = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showCurrent, setShowCurrent]         = useState(false)
  const [showNew, setShowNew]                 = useState(false)
  const [showConfirm, setShowConfirm]         = useState(false)
  const [loading, setLoading]                 = useState(false)
  const [error, setError]                     = useState('')

  const reset = () => {
    setCurrentPassword('')
    setNewPassword('')
    setConfirmPassword('')
    setError('')
    setShowCurrent(false)
    setShowNew(false)
    setShowConfirm(false)
  }

  const handleClose = () => {
    reset()
    onClose()
  }

  const validate = (): string => {
    if (!currentPassword) return 'Current password is required.'
    if (!newPassword)     return 'New password is required.'
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
      await authApi.changePassword({ current_password: currentPassword, new_password: newPassword })
      toast.success('Password updated successfully')
      handleClose()
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem' }}>
      {/* Backdrop */}
      <div
        style={{ position: 'absolute', inset: 0, backgroundColor: 'rgba(15,23,42,0.45)', backdropFilter: 'blur(4px)' }}
        onClick={handleClose}
      />

      {/* Card */}
      <div style={{ position: 'relative', width: '100%', maxWidth: '420px', backgroundColor: '#fff', borderRadius: '16px', boxShadow: '0 20px 60px rgba(0,0,0,0.15)', padding: '2.25rem 2rem 2rem' }}>

        {/* Icon */}
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '1.25rem' }}>
          <div style={{ width: '64px', height: '64px', borderRadius: '50%', backgroundColor: '#EBF0FF', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Lock size={28} color="#4F6FE8" strokeWidth={2} />
          </div>
        </div>

        {/* Title + subtitle */}
        <h2 style={{ margin: 0, textAlign: 'center', fontSize: '1.375rem', fontWeight: 700, color: '#111827' }}>
          Change Password
        </h2>
        <p style={{ margin: '0.5rem 0 1.75rem', textAlign: 'center', fontSize: '0.875rem', color: '#6B7280', lineHeight: 1.5 }}>
          Enter your current password and choose a new secure password
        </p>

        {/* Error */}
        {error && (
          <div style={{ marginBottom: '1rem', padding: '0.75rem 1rem', borderRadius: '10px', backgroundColor: '#FEF2F2', border: '1px solid #FECACA', color: '#DC2626', fontSize: '0.85rem' }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.125rem' }}>

          {/* Current Password */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
            <label style={{ fontSize: '0.875rem', fontWeight: 600, color: '#111827' }}>Current Password</label>
            <div style={{ position: 'relative' }}>
              <input
                type={showCurrent ? 'text' : 'password'}
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                placeholder="Enter current password"
                disabled={loading}
                style={inputStyle}
              />
              <button type="button" onClick={() => setShowCurrent(!showCurrent)} style={eyeBtn}>
                {showCurrent ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>

          {/* New Password */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
            <label style={{ fontSize: '0.875rem', fontWeight: 600, color: '#111827' }}>New Password</label>
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
            <label style={{ fontSize: '0.875rem', fontWeight: 600, color: '#111827' }}>Confirm New Password</label>
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
              backgroundColor: loading ? '#9CA3AF' : '#4B5563',
              color: '#fff',
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
              ? <><span style={{ width: '16px', height: '16px', border: '2px solid rgba(255,255,255,0.3)', borderTopColor: '#fff', borderRadius: '50%', animation: 'spin 0.7s linear infinite', display: 'inline-block' }} /> Saving…</>
              : 'Change Password'
            }
          </button>
        </form>
      </div>
    </div>
  )
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '0.7rem 2.75rem 0.7rem 0.875rem',
  borderRadius: '10px',
  border: '1px solid #E5E7EB',
  backgroundColor: '#F3F4F6',
  fontSize: '0.9rem',
  color: '#111827',
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
  color: '#9CA3AF',
  display: 'flex',
  alignItems: 'center',
  padding: 0,
}
