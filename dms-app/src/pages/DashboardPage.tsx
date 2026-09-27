import { ROLE_LABELS } from '@/utils/permissions'
import { useAuthStore } from '@/store/authStore'
import CategorySetupPanel from '@/components/categories/CategorySetupPanel'
import type { RoleName } from '@/types/user.types'

export default function DashboardPage() {
  const { user } = useAuthStore()

  const primaryRole = user?.roles[0]

  return (
    <div>
      {/* Welcome banner */}
      <div className="card" style={{ padding: '1.25rem 1.5rem', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text)', margin: 0 }}>
            Welcome back, {user?.full_name}
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', margin: '3px 0 0' }}>
            Select a category below to browse documents.
          </p>
        </div>
        {primaryRole && (
          <span className="badge">
            {ROLE_LABELS[primaryRole.name as RoleName] ?? primaryRole.name}
          </span>
        )}
      </div>

      <CategorySetupPanel />
    </div>
  )
}
