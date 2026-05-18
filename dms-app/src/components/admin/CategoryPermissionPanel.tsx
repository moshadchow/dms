import { useCallback, useEffect, useMemo, useState } from 'react'
import { CheckSquare, FolderLock, Search, ShieldCheck, Users } from 'lucide-react'
import { toast } from 'react-hot-toast'
import { categoriesApi } from '@/api/categories.api'
import { getErrorMessage } from '@/api/client'
import { usersApi } from '@/api/users.api'
import Badge from '@/components/ui/Badge'
import Button from '@/components/ui/Button'
import EmptyState from '@/components/ui/EmptyState'
import Spinner from '@/components/ui/Spinner'
import { useAuthStore } from '@/store/authStore'
import type { Category } from '@/types/category.types'
import type { RoleName, User } from '@/types/user.types'

interface Props {
  onUserUpdated?: () => void
}

export default function CategoryPermissionPanel({ onUserUpdated }: Props) {
  const authUser = useAuthStore((state) => state.user)
  const setAuthUser = useAuthStore((state) => state.setUser)

  const [users, setUsers] = useState<User[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [userSearch, setUserSearch] = useState('')
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null)
  const [selectedCategoryIds, setSelectedCategoryIds] = useState<number[]>([])
  const [originalCategoryIds, setOriginalCategoryIds] = useState<number[]>([])
  const [loadingUsers, setLoadingUsers] = useState(true)
  const [loadingCategories, setLoadingCategories] = useState(true)
  const [saving, setSaving] = useState(false)

  const loadCategories = useCallback(async () => {
    setLoadingCategories(true)
    try {
      const data = await categoriesApi.list(true)
      setCategories(data)
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setLoadingCategories(false)
    }
  }, [])

  const loadUsers = useCallback(async (search = '') => {
    setLoadingUsers(true)
    try {
      const data = await usersApi.list({
        limit: 200,
        search: search.trim() || undefined,
      })
      setUsers(data.items)
      setSelectedUserId((current) => {
        if (current && data.items.some((user) => user.id === current)) return current
        return data.items[0]?.id ?? null
      })
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setLoadingUsers(false)
    }
  }, [])

  useEffect(() => {
    loadCategories()
  }, [loadCategories])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      loadUsers(userSearch)
    }, 200)

    return () => window.clearTimeout(timer)
  }, [loadUsers, userSearch])

  const selectedUser = useMemo(
    () => users.find((user) => user.id === selectedUserId) ?? null,
    [selectedUserId, users]
  )

  useEffect(() => {
    if (!selectedUser) {
      setSelectedCategoryIds([])
      setOriginalCategoryIds([])
      return
    }

    const assignedIds = selectedUser.categories.map((category) => category.id).sort((a, b) => a - b)
    setSelectedCategoryIds(assignedIds)
    setOriginalCategoryIds(assignedIds)
  }, [selectedUser])

  const isDirty = useMemo(() => {
    if (selectedCategoryIds.length !== originalCategoryIds.length) return true
    return selectedCategoryIds.some((id, index) => id !== originalCategoryIds[index])
  }, [originalCategoryIds, selectedCategoryIds])

  const toggleCategory = (categoryId: number) => {
    setSelectedCategoryIds((current) => {
      const next = current.includes(categoryId)
        ? current.filter((id) => id !== categoryId)
        : [...current, categoryId]

      return next.sort((a, b) => a - b)
    })
  }

  const handleSave = async () => {
    if (!selectedUser) return

    setSaving(true)
    try {
      const updatedUser = await usersApi.update(selectedUser.id, {
        category_ids: selectedCategoryIds,
      })

      setUsers((current) =>
        current.map((user) => (user.id === updatedUser.id ? updatedUser : user))
      )
      const updatedIds = updatedUser.categories.map((category) => category.id).sort((a, b) => a - b)
      setSelectedCategoryIds(updatedIds)
      setOriginalCategoryIds(updatedIds)

      if (authUser?.id === updatedUser.id) {
        setAuthUser(updatedUser)
      }

      onUserUpdated?.()
      toast.success('Category permissions saved')
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  const assignedCount = selectedCategoryIds.length

  return (
    <div style={{ padding: '1.25rem' }}>
      <div style={{ marginBottom: '1.25rem' }}>
        <h3 style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--text)', margin: 0 }}>
          Category-wise user access
        </h3>
        <p style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)', margin: '0.3rem 0 0' }}>
          Select a user, assign the categories they can see, then save the full access map.
        </p>
      </div>

      <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
        <section style={{ ...panelStyle, flex: '1 1 280px', maxWidth: '320px' }}>
          <div style={{ padding: '1rem', borderBottom: '1px solid var(--border)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.85rem' }}>
              <div style={iconWrapStyle}>
                <Users size={16} color="#475569" />
              </div>
              <div>
                <p style={{ fontSize: '0.84rem', fontWeight: 700, color: 'var(--text)', margin: 0 }}>
                  Select user
                </p>
                <p style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', margin: '0.15rem 0 0' }}>
                  Search by name or email
                </p>
              </div>
            </div>

            <div style={{ position: 'relative' }}>
              <Search size={14} color="#94a3b8" style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)' }} />
              <input
                className="input"
                value={userSearch}
                onChange={(event) => setUserSearch(event.target.value)}
                placeholder="Search users..."
                style={{ paddingLeft: '32px', fontSize: '0.82rem' }}
              />
            </div>
          </div>

          <div style={{ maxHeight: '520px', overflowY: 'auto', padding: '0.5rem' }}>
            {loadingUsers ? (
              <div style={{ padding: '1rem', display: 'flex', justifyContent: 'center' }}>
                <Spinner />
              </div>
            ) : users.length === 0 ? (
              <EmptyState
                compact
                icon={<Users size={30} color="#cbd5e1" />}
                title="No users found"
                description="Try a different search term."
              />
            ) : (
              users.map((user) => {
                const isSelected = user.id === selectedUserId
                const primaryRole = user.roles[0]?.name as RoleName | undefined

                return (
                  <button
                    key={user.id}
                    type="button"
                    onClick={() => setSelectedUserId(user.id)}
                    style={{
                      width: '100%',
                      textAlign: 'left',
                      padding: '0.85rem',
                      borderRadius: '0.75rem',
                      border: `1px solid ${isSelected ? '#6366f1' : 'var(--border)'}`,
                      backgroundColor: isSelected ? 'var(--primary-soft)' : 'var(--surface)',
                      cursor: 'pointer',
                      marginBottom: '0.45rem',
                      fontFamily: 'inherit',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.75rem' }}>
                      <div style={{ minWidth: 0 }}>
                        <p style={{ margin: 0, fontSize: '0.84rem', fontWeight: 700, color: isSelected ? '#4338ca' : 'var(--text)' }}>
                          {user.full_name}
                        </p>
                        <p style={{ margin: '0.2rem 0 0', fontSize: '0.74rem', color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {user.email}
                        </p>
                      </div>
                      <span style={{
                        flexShrink: 0,
                        padding: '2px 8px',
                        borderRadius: '999px',
                        backgroundColor: user.is_active ? '#f0fdf4' : '#fef2f2',
                        color: user.is_active ? '#16a34a' : '#dc2626',
                        fontSize: '0.68rem',
                        fontWeight: 700,
                      }}>
                        {user.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', marginTop: '0.65rem', flexWrap: 'wrap' }}>
                      {primaryRole && <Badge variant="role" role={primaryRole} />}
                      <span style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', fontWeight: 600 }}>
                        {user.categories.length} categories assigned
                      </span>
                    </div>
                  </button>
                )
              })
            )}
          </div>
        </section>

        <section style={{ ...panelStyle, flex: '2 1 520px' }}>
          <div style={{ padding: '1rem', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                <div style={iconWrapStyle}>
                  <ShieldCheck size={16} color="#475569" />
                </div>
                <div>
                  <p style={{ fontSize: '0.84rem', fontWeight: 700, color: 'var(--text)', margin: 0 }}>
                    {selectedUser ? selectedUser.full_name : 'Choose a user'}
                  </p>
                  <p style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', margin: '0.15rem 0 0' }}>
                    {selectedUser ? `${assignedCount} categories assigned` : 'Category assignment will appear here'}
                  </p>
                </div>
              </div>
              {selectedUser && (
                <div style={{ display: 'flex', gap: '0.45rem', marginTop: '0.75rem', flexWrap: 'wrap' }}>
                  {selectedUser.roles.map((role) => (
                    <Badge key={role.id} variant="role" role={role.name as RoleName} />
                  ))}
                </div>
              )}
            </div>

            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              <Button
                variant="secondary"
                size="sm"
                disabled={!selectedUser || selectedCategoryIds.length === 0 || saving}
                onClick={() => setSelectedCategoryIds([])}
              >
                Clear all
              </Button>
              <Button
                size="sm"
                icon={<CheckSquare size={14} />}
                loading={saving}
                disabled={!selectedUser || !isDirty}
                onClick={handleSave}
              >
                Save permissions
              </Button>
            </div>
          </div>

          <div style={{ padding: '1rem' }}>
            {!selectedUser ? (
              <EmptyState
                icon={<FolderLock size={34} color="#cbd5e1" />}
                title="No user selected"
                description="Pick a user from the list to assign category access."
              />
            ) : loadingCategories ? (
              <div style={{ display: 'flex', justifyContent: 'center', padding: '3rem 0' }}>
                <Spinner size="lg" />
              </div>
            ) : categories.length === 0 ? (
              <EmptyState
                icon={<FolderLock size={34} color="#cbd5e1" />}
                title="No categories available"
                description="Create categories first, then assign them to users."
              />
            ) : (
              <>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0.75rem' }}>
                  {categories.map((category) => {
                    const checked = selectedCategoryIds.includes(category.id)
                    return (
                      <button
                        key={category.id}
                        type="button"
                        onClick={() => toggleCategory(category.id)}
                        style={{
                          textAlign: 'left',
                          padding: '0.9rem',
                          borderRadius: '0.85rem',
                          border: `1.5px solid ${checked ? '#6366f1' : 'var(--border)'}`,
                          backgroundColor: checked ? 'var(--primary-soft)' : 'var(--surface)',
                          cursor: 'pointer',
                          fontFamily: 'inherit',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '0.75rem' }}>
                          <div style={{ minWidth: 0 }}>
                            <p style={{ margin: 0, fontSize: '0.84rem', fontWeight: 700, color: checked ? '#4338ca' : 'var(--text)' }}>
                              {category.name}
                            </p>
                            {category.description && (
                              <p style={{ margin: '0.3rem 0 0', fontSize: '0.74rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                                {category.description}
                              </p>
                            )}
                          </div>
                          <div style={{
                            width: '18px',
                            height: '18px',
                            borderRadius: '5px',
                            border: `2px solid ${checked ? '#6366f1' : 'var(--border-soft)'}`,
                            backgroundColor: checked ? '#6366f1' : 'transparent',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            flexShrink: 0,
                          }}>
                            {checked && <CheckSquare size={11} color="#ffffff" />}
                          </div>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', marginTop: '0.8rem', flexWrap: 'wrap' }}>
                          <span style={metaPillStyle}>
                            {category.directory_count} dirs
                          </span>
                          <span style={metaPillStyle}>
                            {category.document_count} docs
                          </span>
                          {!category.is_active && (
                            <span style={{ ...metaPillStyle, backgroundColor: '#fef2f2', color: '#dc2626' }}>
                              Inactive
                            </span>
                          )}
                        </div>
                      </button>
                    )
                  })}
                </div>

                <div style={{ marginTop: '1rem', padding: '0.85rem 1rem', borderRadius: '0.85rem', backgroundColor: 'var(--bg)', border: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                    <FolderLock size={15} color="#64748b" />
                    <p style={{ margin: 0, fontSize: '0.76rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                      Only categories selected here should appear in the user dashboard and sidebar. Unassigned categories stay hidden and direct navigation should resolve to access denied.
                    </p>
                  </div>
                </div>
              </>
            )}
          </div>
        </section>
      </div>
    </div>
  )
}

const panelStyle: React.CSSProperties = {
  backgroundColor: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: '1rem',
  overflow: 'hidden',
  minWidth: 0,
}

const iconWrapStyle: React.CSSProperties = {
  width: '32px',
  height: '32px',
  borderRadius: '8px',
  backgroundColor: 'var(--bg)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  flexShrink: 0,
}

const metaPillStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  padding: '2px 8px',
  borderRadius: '999px',
  backgroundColor: 'var(--bg)',
  color: 'var(--text-secondary)',
  fontSize: '0.68rem',
  fontWeight: 700,
}
