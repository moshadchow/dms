import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'react-hot-toast'
import { useAuthStore } from '@/store/authStore'
import { ROLE_LABELS } from '@/utils/permissions'
import type { RoleName } from '@/types/user.types'
import ThemeToggle from '@/components/ui/ThemeToggle'

interface Props {
  onMenuToggle:     () => void
  sidebarOpen:      boolean
  onChangePassword: () => void
}

export default function Topbar({ onMenuToggle, sidebarOpen, onChangePassword }: Props) {
  const navigate = useNavigate()
  const { user, logout, isAdmin } = useAuthStore()
  const [dropdownOpen, setDropdownOpen] = useState(false)

  const handleLogout = () => {
    logout()
    toast.success('Logged out successfully')
    navigate('/login', { replace: true })
  }

  const primaryRole = user?.roles[0]
  const initials = user?.full_name
    .split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2) ?? '?'

  return (
    <>
      <header style={{
        height: '60px',
        backgroundColor: 'var(--topbar-bg)',
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 1.25rem',
        position: 'sticky', top: 0, zIndex: 40, flexShrink: 0,
        transition: 'background-color 200ms',
      }}>

        {/* Left — hamburger + logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <button onClick={onMenuToggle} style={{ width: '36px', height: '36px', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '8px', border: 'none', backgroundColor: 'transparent', cursor: 'pointer', color: 'var(--text-secondary)' }}>
            {sidebarOpen
              ? <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              : <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
            }
          </button>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{ width: '30px', height: '30px', backgroundColor: 'var(--text)', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--surface)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
              </svg>
            </div>
            <span style={{ fontWeight: 700, fontSize: '1rem', color: 'var(--text)', letterSpacing: '-0.02em' }}>DMS</span>
          </div>
        </div>

        {/* Right — theme toggle + admin link + user menu */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>

          {/* Theme toggle */}
          <ThemeToggle />

          {isAdmin() && (
            <button onClick={() => navigate('/admin')} style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 12px', backgroundColor: 'var(--surface-2)', border: '1px solid var(--border-soft)', borderRadius: '8px', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', cursor: 'pointer', fontFamily: 'inherit' }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
              Admin
            </button>
          )}

          {/* User avatar */}
          <div style={{ position: 'relative' }}>
            <button
              onClick={() => setDropdownOpen(!dropdownOpen)}
              style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 10px', backgroundColor: dropdownOpen ? 'var(--surface-2)' : 'transparent', border: `1px solid ${dropdownOpen ? 'var(--border-soft)' : 'transparent'}`, borderRadius: '10px', cursor: 'pointer', fontFamily: 'inherit' }}
            >
              <div style={{ width: '32px', height: '32px', backgroundColor: 'var(--text)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.75rem', fontWeight: 700, color: 'var(--surface)', flexShrink: 0 }}>
                {initials}
              </div>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="2">
                <polyline points="6 9 12 15 18 9"/>
              </svg>
            </button>

            {dropdownOpen && (
              <div style={{ position: 'absolute', right: 0, top: 'calc(100% + 6px)', width: '220px', backgroundColor: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '12px', boxShadow: 'var(--shadow-lg)', overflow: 'hidden', zIndex: 50, padding: '0.3rem' }}>
                {/* User info */}
                <div style={{ padding: '0.875rem 1rem', borderBottom: '1px solid var(--border)' }}>
                  <p style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--text)', margin: 0 }}>{user?.full_name}</p>
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', margin: '2px 0 0' }}>{user?.email}</p>
                  {primaryRole && (
                    <span style={{ display: 'inline-block', marginTop: '6px', padding: '2px 8px', borderRadius: '999px', fontSize: '0.7rem', fontWeight: 600, backgroundColor: 'var(--surface-2)', color: 'var(--text-secondary)' }}>
                      {ROLE_LABELS[primaryRole.name as RoleName] ?? primaryRole.name}
                    </span>
                  )}
                </div>

                {/* Menu items */}
                <div style={{ padding: '0.375rem' }}>
                  <button onClick={() => { setDropdownOpen(false); onChangePassword() }} style={menuItem('var(--text-secondary)')}>
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                    Change password
                  </button>
                  <div style={{ height: '1px', backgroundColor: 'var(--border)', margin: '0.25rem 0' }} />
                  <button onClick={() => { setDropdownOpen(false); handleLogout() }} style={menuItem('var(--danger)')}>
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
                    Sign out
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      {dropdownOpen && <div style={{ position: 'fixed', inset: 0, zIndex: 30 }} onClick={() => setDropdownOpen(false)} />}
    </>
  )
}

const menuItem = (color: string): React.CSSProperties => ({
  width: '100%', display: 'flex', alignItems: 'center', gap: '8px',
  padding: '0.5rem 0.625rem', borderRadius: '8px', border: 'none',
  backgroundColor: 'transparent', fontSize: '0.85rem', fontWeight: 500,
  color, cursor: 'pointer', textAlign: 'left', fontFamily: 'inherit',
})
