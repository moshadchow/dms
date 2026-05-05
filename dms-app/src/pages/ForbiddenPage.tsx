import { useNavigate } from 'react-router-dom'

export default function ForbiddenPage() {
  const navigate = useNavigate()

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f8fafc', padding: '2rem' }}>
      <div style={{ textAlign: 'center', maxWidth: '400px' }}>
        <div style={{ fontSize: '7rem', fontWeight: 800, color: '#fef2f2', lineHeight: 1, marginBottom: '0.5rem', letterSpacing: '-4px' }}>
          403
        </div>
        <div style={{ width: '64px', height: '64px', backgroundColor: '#fff', borderRadius: '16px', border: '1px solid #fecaca', boxShadow: '0 4px 16px rgba(0,0,0,0.06)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 1.5rem' }}>
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="1.5">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
            <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
          </svg>
        </div>
        <h1 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#1e293b', margin: '0 0 0.5rem' }}>Access denied</h1>
        <p style={{ color: '#94a3b8', fontSize: '0.875rem', margin: '0 0 2rem', lineHeight: 1.6 }}>
          You don't have permission to view this page. Contact your administrator if you think this is a mistake.
        </p>
        <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center' }}>
          <button onClick={() => navigate(-1)} style={{ padding: '8px 18px', backgroundColor: '#f8fafc', color: '#374151', border: '1px solid #e2e8f0', borderRadius: '8px', fontSize: '0.875rem', fontWeight: 500, cursor: 'pointer', fontFamily: 'inherit' }}>
            ← Go back
          </button>
          <button onClick={() => navigate('/dashboard')} style={{ padding: '8px 18px', backgroundColor: '#1e293b', color: '#fff', border: 'none', borderRadius: '8px', fontSize: '0.875rem', fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}>
            Dashboard
          </button>
        </div>
      </div>
    </div>
  )
}
