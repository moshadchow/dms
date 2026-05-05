import { Routes, Route, Navigate } from 'react-router-dom'
import { Suspense, lazy, Component, type ReactNode } from 'react'
import ProtectedRoute from '@/components/auth/ProtectedRoute'
import AppLayout from '@/components/layout/AppLayout'
import Spinner from '@/components/ui/Spinner'

const LoginPage     = lazy(() => import('@/pages/LoginPage'))
const DashboardPage = lazy(() => import('@/pages/DashboardPage'))
const DocumentsPage = lazy(() => import('@/pages/DocumentsPage'))
const AdminPage     = lazy(() => import('@/pages/AdminPage'))
const NotFoundPage  = lazy(() => import('@/pages/NotFoundPage'))
const ForbiddenPage = lazy(() => import('@/pages/ForbiddenPage'))

function PageLoader() {
  return (
    <div style={{ display: 'flex', height: '100vh', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f8fafc' }}>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}>
        <Spinner size="lg" />
        <p style={{ color: '#94a3b8', fontSize: '0.85rem' }}>Loading…</p>
      </div>
    </div>
  )
}

// ── Error Boundary ────────────────────────────────────────────────
interface EBState { hasError: boolean; message: string }
class ErrorBoundary extends Component<{ children: ReactNode }, EBState> {
  state: EBState = { hasError: false, message: '' }

  static getDerivedStateFromError(error: Error): EBState {
    return { hasError: true, message: error.message }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ display: 'flex', height: '100vh', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f8fafc', padding: '2rem' }}>
          <div style={{ textAlign: 'center', maxWidth: '400px' }}>
            <div style={{ width: '56px', height: '56px', backgroundColor: '#fef2f2', borderRadius: '14px', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 1rem' }}>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="8" x2="12" y2="12"/>
                <line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
            </div>
            <h2 style={{ fontWeight: 700, color: '#1e293b', margin: '0 0 0.5rem' }}>Something went wrong</h2>
            <p style={{ color: '#94a3b8', fontSize: '0.875rem', margin: '0 0 1.5rem' }}>{this.state.message}</p>
            <button
              onClick={() => window.location.reload()}
              style={{ padding: '8px 18px', backgroundColor: '#1e293b', color: '#fff', border: 'none', borderRadius: '8px', fontSize: '0.875rem', fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}
            >
              Reload page
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

// ── App ───────────────────────────────────────────────────────────
export default function App() {
  return (
    <ErrorBoundary>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          {/* Public */}
          <Route path="/login"     element={<LoginPage />} />
          <Route path="/forbidden" element={<ForbiddenPage />} />

          {/* Authenticated */}
          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              <Route index                        element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard"            element={<DashboardPage />} />
              <Route path="/directory/:directoryId" element={<DocumentsPage />} />
              <Route path="/admin"                element={<AdminPage />} />
            </Route>
          </Route>

          {/* Catch-all */}
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </Suspense>
    </ErrorBoundary>
  )
}
