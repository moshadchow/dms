import { useEffect, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { toast } from 'react-hot-toast'
import { categoriesApi } from '@/api/categories.api'
import { useDirectoryStore } from '@/store/directoryStore'
import { useAuthStore } from '@/store/authStore'
import type { Category } from '@/types/category.types'

interface Props { isOpen: boolean }

export default function Sidebar({ isOpen }: Props) {
  const navigate = useNavigate()
  const location = useLocation()
  const { isAdmin, user } = useAuthStore()
  const { categoriesVersion, setSelectedCategory } = useDirectoryStore()

  const [categories, setCategories]   = useState<Category[]>([])
  const [loadingCats, setLoadingCats] = useState(true)

  // Active category from URL — handles both /directory/{catId}?root=true
  // and /directory/{dirId} (non-root, we keep whichever cat was last set)
  const activeCatId = (() => {
    const match  = location.pathname.match(/\/directory\/(\d+)/)
    const isRoot = location.search.includes('root=true')
    if (match && isRoot) return parseInt(match[1])
    return null
  })()

  // Load categories whenever categoriesVersion bumps
  useEffect(() => {
    setLoadingCats(true)
    // Match dashboard: admins see inactive categories too
    categoriesApi.list(isAdmin())
      .then(setCategories)
      .catch(() => toast.error('Failed to load categories'))
      .finally(() => setLoadingCats(false))
  }, [categoriesVersion, user?.id])  // re-fetch when user profile loads

  const handleCategoryClick = (cat: Category) => {
    setSelectedCategory(cat.id)
    navigate(`/directory/${cat.id}?root=true`)
  }

  return (
    <aside style={{
      width: isOpen ? '240px' : '0px',
      minWidth: isOpen ? '240px' : '0px',
      overflow: 'hidden',
      transition: 'width 200ms ease, min-width 200ms ease',
      backgroundColor: 'var(--sidebar-bg)',
      borderRight: '1px solid var(--surface-2)',
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
    }}>
      <div style={{ width: '240px', height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

        {/* Section label */}
        <div style={{ padding: '1rem 1rem 0.5rem', flexShrink: 0 }}>
          <p style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-tertiary)', margin: 0 }}>
            Categories
          </p>
        </div>

        {/* Category list — flat, no directories */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '0.25rem 0.5rem' }}>
          {loadingCats ? (
            <div style={{ padding: '1rem', display: 'flex', justifyContent: 'center' }}>
              <Spin />
            </div>
          ) : categories.length === 0 ? (
            <p style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-tertiary)', fontSize: '0.8rem', margin: 0 }}>
              No categories yet
            </p>
          ) : (
            categories.map((cat) => {
              const isActive = activeCatId === cat.id

              return (
                <button
                  key={cat.id}
                  onClick={() => handleCategoryClick(cat)}
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    padding: '8px 10px',
                    borderRadius: '8px',
                    border: 'none',
                    backgroundColor: isActive ? 'var(--primary-soft)' : 'transparent',
                    cursor: 'pointer',
                    textAlign: 'left',
                    fontFamily: 'inherit',
                    marginBottom: '2px',
                  }}
                >
                  {/* Folder icon */}
                  <div style={{
                    width: '28px', height: '28px', flexShrink: 0,
                    backgroundColor: isActive ? 'var(--primary-soft)' : 'var(--surface-2)',
                    borderRadius: '7px',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    border: `1px solid ${isActive ? 'var(--primary)' : 'var(--border)'}`,
                  }}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                      stroke={isActive ? 'var(--primary)' : 'var(--text-tertiary)'} strokeWidth="2">
                      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                    </svg>
                  </div>

                  {/* Name + doc count */}
                  <div style={{ flex: 1, overflow: 'hidden' }}>
                    <p style={{
                      fontSize: '0.85rem',
                      fontWeight: isActive ? 700 : 500,
                      color: isActive ? 'var(--primary)' : 'var(--text)',
                      margin: 0,
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                      {cat.name}
                    </p>
                    <p style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', margin: '1px 0 0' }}>
                      {cat.directory_count} dir · {cat.document_count} docs
                    </p>
                  </div>

                  {/* Active indicator */}
                  {isActive && (
                    <div style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: 'var(--primary)', flexShrink: 0 }} />
                  )}
                </button>
              )
            })
          )}
        </div>

        {/* Bottom nav */}
        <div style={{ borderTop: '1px solid var(--border)', padding: '0.5rem' }}>
          <NavBtn
            label="Dashboard"
            onClick={() => navigate('/dashboard')}
            icon={<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>}
            active={location.pathname === '/dashboard'}
          />
          {isAdmin() && (
            <NavBtn
              label="Admin panel"
              onClick={() => navigate('/admin')}
              icon={<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>}
              active={location.pathname === '/admin'}
            />
          )}
        </div>

        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    </aside>
  )
}

function Spin({ small }: { small?: boolean }) {
  const s = small ? 14 : 20
  return (
    <div style={{ width: s, height: s, border: '2px solid var(--surface-3)', borderTopColor: 'var(--primary)', borderRadius: '50%', animation: 'spin 0.7s linear infinite', flexShrink: 0 }} />
  )
}

function NavBtn({ icon, label, onClick, active }: { icon: React.ReactNode; label: string; onClick: () => void; active?: boolean }) {
  return (
    <button
      onClick={onClick}
      style={{
        width: '100%', display: 'flex', alignItems: 'center', gap: '8px',
        padding: '7px 8px', borderRadius: '8px', border: 'none',
        backgroundColor: active ? 'var(--surface-2)' : 'transparent',
        cursor: 'pointer', textAlign: 'left',
        fontSize: '0.85rem', fontWeight: active ? 600 : 500,
        color: active ? 'var(--text)' : 'var(--text-secondary)',
        fontFamily: 'inherit',
        marginBottom: '2px',
      }}
    >
      {icon}{label}
    </button>
  )
}
