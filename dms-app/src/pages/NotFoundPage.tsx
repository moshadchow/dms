import { useNavigate } from 'react-router-dom'

export default function NotFoundPage() {
  const navigate = useNavigate()

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f8fafc', padding: '2rem' }}>
      <div style={{ textAlign: 'center', maxWidth: '400px' }}>
        <div style={{ fontSize: '7rem', fontWeight: 800, color: '#f1f5f9', lineHeight: 1, marginBottom: '0.5rem', letterSpacing: '-4px' }}>
          404
        </div>
        <div style={{ width: '64px', height: '64px', backgroundColor: '#fff', borderRadius: '16px', border: '1px solid #f1f5f9', boxShadow: '0 4px 16px rgba(0,0,0,0.06)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 1.5rem' }}>
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="1.5">
            <circle cx="12" cy="12" r="10"/>
            <line x1="12" y1="8" x2="12" y2="12"/>
            <line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
        </div>
        <h1 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#1e293b', margin: '0 0 0.5rem' }}>Page not found</h1>
        <p style={{ color: '#94a3b8', fontSize: '0.875rem', margin: '0 0 2rem', lineHeight: 1.6 }}>
          The page you're looking for doesn't exist or has been moved.
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
