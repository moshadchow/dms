import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'react-hot-toast'
import { categoriesApi } from '@/api/categories.api'
import { useAuthStore } from '@/store/authStore'
import { useDirectoryStore } from '@/store/directoryStore'
import { getErrorMessage } from '@/api/client'
import CategoryCard from '@/components/categories/CategoryCard'
import CategoryFormModal from '@/components/categories/CategoryFormModal'
import ConfirmDialog from '@/components/ui/ConfirmDialog'
import type { Category } from '@/types/category.types'
import { ROLE_LABELS } from '@/utils/permissions'
import type { RoleName } from '@/types/user.types'

export default function DashboardPage() {
  const navigate  = useNavigate()
  const { user, isAdmin } = useAuthStore()
  const { setSelectedCategory, refreshCategories } = useDirectoryStore()

  const [categories, setCategories] = useState<Category[]>([])
  const [loading, setLoading]       = useState(true)
  const [formOpen, setFormOpen]     = useState(false)
  const [editing, setEditing]       = useState<Category | null>(null)
  const [deleting, setDeleting]     = useState<Category | null>(null)
  const [deleteLoading, setDeleteLoading] = useState(false)

  const primaryRole = user?.roles[0]

  const loadCategories = useCallback(async () => {
    try {
      const data = await categoriesApi.list(isAdmin())
      setCategories(data)
    } catch {
      toast.error('Failed to load categories')
    } finally {
      setLoading(false)
    }
  }, [isAdmin])

  useEffect(() => { loadCategories() }, [loadCategories])

  const handleCategoryClick = (cat: Category) => {
    setSelectedCategory(cat.id)
    navigate(`/directory/${cat.id}?root=true`)
  }

  const handleFormSuccess = (cat: Category) => {
    setCategories((prev) =>
      editing
        // Merge updated fields into existing entry so directory_count
        // and document_count (not returned by PATCH) are preserved
        ? prev.map((c) => (c.id === cat.id ? { ...c, ...cat } : c))
        : [...prev, { ...cat, directory_count: 0, document_count: 0 }]
    )
    refreshCategories()   // triggers sidebar reload
  }

  const handleDeleteConfirm = async () => {
    if (!deleting) return
    setDeleteLoading(true)
    try {
      await categoriesApi.delete(deleting.id)
      setCategories((prev) => prev.filter((c) => c.id !== deleting.id))
      refreshCategories()
      toast.success('Category deleted')
      setDeleting(null)
    } catch (err) {
      const msg = getErrorMessage(err)
      // Backend blocks delete when directories exist — offer to deactivate instead
      if (msg.includes('directories') || msg.includes('Archive')) {
        toast.error(
          `Cannot delete — this category has directories. Use Edit to deactivate it instead.`,
          { duration: 5000 }
        )
      } else {
        toast.error(msg)
      }
      setDeleting(null)
    } finally {
      setDeleteLoading(false)
    }
  }

  return (
    <div>
      {/* Welcome banner */}
      <div style={{ backgroundColor: 'var(--surface)', borderRadius: '1rem', border: '1px solid var(--border)', padding: '1.25rem 1.5rem', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text)', margin: 0 }}>
            Welcome back, {user?.full_name} 👋
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', margin: '3px 0 0' }}>
            Select a category below to browse documents.
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          {primaryRole && (
            <span style={{ padding: '5px 12px', borderRadius: '999px', backgroundColor: 'var(--surface-2)', color: 'var(--text-secondary)', fontSize: '0.78rem', fontWeight: 600 }}>
              {ROLE_LABELS[primaryRole.name as RoleName] ?? primaryRole.name}
            </span>
          )}
          {isAdmin() && (
            <button
              onClick={() => { setEditing(null); setFormOpen(true) }}
              style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '7px 14px', backgroundColor: 'var(--text)', color: 'var(--surface)', border: 'none', borderRadius: '8px', fontSize: '0.85rem', fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
              New category
            </button>
          )}
        </div>
      </div>

      {/* Stats bar */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.75rem', marginBottom: '1.5rem' }}>
        {[
          { label: 'Total categories', value: categories.length, color: 'var(--primary)' },
          { label: 'Total directories', value: categories.reduce((s, c) => s + (c.directory_count ?? 0), 0), color: 'var(--info)' },
          { label: 'Total documents', value: categories.reduce((s, c) => s + (c.document_count ?? 0), 0), color: 'var(--success)' },
        ].map((stat) => (
          <div key={stat.label} style={{ backgroundColor: 'var(--surface)', borderRadius: '0.875rem', border: '1px solid var(--border)', padding: '1rem 1.25rem' }}>
            <p style={{ fontSize: '1.5rem', fontWeight: 700, color: stat.color, margin: 0 }}>{stat.value}</p>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)', margin: '2px 0 0', fontWeight: 500 }}>{stat.label}</p>
          </div>
        ))}
      </div>

      {/* Section header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
        <h2 style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.06em', margin: 0 }}>
          Categories
        </h2>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{categories.length} total</span>
      </div>

      {/* Category grid */}
      {loading ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '1rem' }}>
          {[...Array(6)].map((_, i) => (
            <div key={i} style={{ backgroundColor: 'var(--surface)', borderRadius: '0.875rem', border: '1px solid var(--border)', padding: '1.25rem', animation: 'pulse 1.5s ease-in-out infinite' }}>
              <div style={{ width: '40px', height: '40px', backgroundColor: 'var(--surface-2)', borderRadius: '10px', marginBottom: '0.875rem' }} />
              <div style={{ height: '14px', backgroundColor: 'var(--surface-2)', borderRadius: '4px', marginBottom: '6px', width: '70%' }} />
              <div style={{ height: '11px', backgroundColor: 'var(--bg)', borderRadius: '4px', width: '50%' }} />
            </div>
          ))}
          <style>{`@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.5} }`}</style>
        </div>
      ) : categories.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '4rem 2rem', backgroundColor: 'var(--surface)', borderRadius: '1rem', border: '1px dashed #e2e8f0' }}>
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" strokeWidth="1.5" style={{ margin: '0 auto 1rem' }}>
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
          </svg>
          <p style={{ fontWeight: 600, color: 'var(--text-tertiary)', margin: 0 }}>No categories yet</p>
          {isAdmin() && (
            <button
              onClick={() => { setEditing(null); setFormOpen(true) }}
              style={{ marginTop: '1rem', padding: '8px 18px', backgroundColor: 'var(--text)', color: 'var(--surface)', border: 'none', borderRadius: '8px', fontSize: '0.875rem', fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}
            >
              Create first category
            </button>
          )}
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '1rem' }}>
          {categories.map((cat) => (
            <CategoryCard
              key={cat.id}
              category={cat}
              isAdmin={isAdmin()}
              onClick={() => handleCategoryClick(cat)}
              onEdit={() => { setEditing(cat); setFormOpen(true) }}
              onDelete={() => setDeleting(cat)}
            />
          ))}
        </div>
      )}

      {/* Modals */}
      <CategoryFormModal
        isOpen={formOpen}
        editing={editing}
        onClose={() => { setFormOpen(false); setEditing(null) }}
        onSuccess={handleFormSuccess}
      />

      <ConfirmDialog
        isOpen={!!deleting}
        title="Delete category"
        message={
          (deleting?.directory_count ?? 0) > 0
            ? `"${deleting?.name}" has ${deleting?.directory_count} director${deleting?.directory_count === 1 ? 'y' : 'ies'} — it cannot be deleted. Delete all directories first, or use Edit → deactivate to hide it instead.`
            : `Permanently delete "${deleting?.name}"? This cannot be undone.`
        }
        confirmLabel={(deleting?.directory_count ?? 0) > 0 ? 'OK, got it' : 'Delete'}
        danger={(deleting?.directory_count ?? 0) === 0}
        loading={deleteLoading}
        onConfirm={(deleting?.directory_count ?? 0) > 0 ? () => setDeleting(null) : handleDeleteConfirm}
        onCancel={() => setDeleting(null)}
      />
    </div>
  )
}
