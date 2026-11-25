import { useEffect, useState, useMemo } from 'react'
import { directoriesApi } from '@/api/directories.api'
import { getErrorMessage } from '@/api/client'
import type { Directory } from '@/types/directory.types'

interface MoveDestinationPickerProps {
  /** Directory being moved (for cycle prevention) */
  excludeDirectoryId?: number
  /** Current document's directory (for document moves - optional no-op prevention) */
  currentDocumentDirectoryId?: number
  /** Called when user selects a destination */
  onSelect: (directoryId: number | null, directoryName: string, categoryName: string) => void
  /** Loading state from parent */
  loading: boolean
  /** Called when modal should close (cancel) */
  onClose: () => void
  /** Categories for display names */
  categories: { id: number; name: string }[]
}

function buildChildrenMap(dirs: Directory[]): Map<number, number[]> {
  const map = new Map<number, number[]>()
  for (const d of dirs) {
    const parentId = d.parent_id ?? -1
    if (!map.has(parentId)) map.set(parentId, [])
    map.get(parentId)!.push(d.id)
  }
  return map
}

function getDescendants(rootId: number, childrenMap: Map<number, number[]>): number[] {
  const result: number[] = []
  const stack = childrenMap.get(rootId) ?? []
  while (stack.length) {
    const id = stack.pop()!
    result.push(id)
    stack.push(...(childrenMap.get(id) ?? []))
  }
  return result
}

export default function MoveDestinationPicker({
  excludeDirectoryId,
  currentDocumentDirectoryId,
  onSelect,
  loading,
  onClose,
  categories,
}: MoveDestinationPickerProps) {
  const [allDirs, setAllDirs] = useState<Directory[]>([])
  const [dirsLoading, setDirsLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedDirId, setSelectedDirId] = useState<number | null>(null)
  const [selectedRootCategoryId, setSelectedRootCategoryId] = useState<number | null>(null)

  useEffect(() => {
    let cancelled = false
    directoriesApi.listAll()
      .then((data) => {
        if (!cancelled) setAllDirs(data)
      })
      .catch((err) => {
        if (!cancelled) setError(getErrorMessage(err))
      })
      .finally(() => {
        if (!cancelled) setDirsLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  const childrenMap = useMemo(() => buildChildrenMap(allDirs), [allDirs])

  const excludedIds = useMemo(() => {
    const set = new Set<number>()
    if (excludeDirectoryId) {
      set.add(excludeDirectoryId)
      getDescendants(excludeDirectoryId, childrenMap).forEach((id) => set.add(id))
    }
    if (currentDocumentDirectoryId) {
      set.add(currentDocumentDirectoryId)
    }
    return set
  }, [excludeDirectoryId, currentDocumentDirectoryId, childrenMap])

  const categoriesWithDirs = useMemo(() => {
    const categoryMap = new Map<number, { name: string; dirs: Directory[] }>()
    for (const cat of categories) {
      categoryMap.set(cat.id, { name: cat.name, dirs: [] })
    }
    for (const dir of allDirs) {
      if (excludedIds.has(dir.id) || dir.navigation_only) continue
      const cat = categoryMap.get(dir.category_id)
      if (cat) cat.dirs.push(dir)
    }
    // Add root option for each category that has accessible directories
    const result: { categoryId: number; categoryName: string; dirs: (Directory & { isRoot?: boolean })[] }[] = []
    for (const [categoryId, { name, dirs }] of categoryMap) {
      if (dirs.length > 0) {
        result.push({ categoryId, categoryName: name, dirs: [{ id: -1, name: 'Root level', isRoot: true, category_id: 0, parent_id: null, created_by: 0, created_at: '', updated_at: '', description: null } as Directory & { isRoot?: boolean }, ...dirs] })
      }
    }
    return result
  }, [allDirs, categories, excludedIds, childrenMap])

  const handleSelectRoot = (categoryId: number) => {
    setSelectedRootCategoryId(categoryId)
    setSelectedDirId(null)
  }

  const handleSelectDir = (dir: Directory) => {
    setSelectedDirId(dir.id)
    setSelectedRootCategoryId(null)
  }

  const handleConfirm = () => {
    if (selectedRootCategoryId !== null) {
      const cat = categories.find((c) => c.id === selectedRootCategoryId)
      onSelect(null, 'Root level', cat?.name ?? '')
    } else if (selectedDirId !== null) {
      const dir = allDirs.find((d) => d.id === selectedDirId)
      if (dir) {
        const cat = categories.find((c) => c.id === dir.category_id)
        onSelect(dir.id, dir.name, cat?.name ?? '')
      }
    }
  }

  if (dirsLoading) {
    return (
      <div style={{ padding: '2rem', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.75rem' }}>
        <div style={{ width: '24px', height: '24px', border: '2px solid var(--border-soft)', borderTopColor: 'var(--primary)', borderRadius: '50%', animation: 'spin 0.7s linear infinite' }} />
        <p style={{ color: 'var(--text-tertiary)', fontSize: '0.85rem', margin: 0 }}>Loading directories...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div style={{ padding: '1rem', color: '#dc2626', fontSize: '0.85rem', textAlign: 'center' }}>
        Failed to load directories: {error}
      </div>
    )
  }

  return (
    <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
      {categoriesWithDirs.length === 0 ? (
        <p style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-tertiary)', fontSize: '0.85rem' }}>
          No accessible destinations found
        </p>
      ) : (
        categoriesWithDirs.map(({ categoryId, categoryName, dirs }) => (
          <div key={categoryId} style={{ marginBottom: '1rem' }}>
            <p style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', margin: '0 0 0.5rem 0.5rem' }}>
              {categoryName}
            </p>
            {dirs.map((dir) => (
              <button
                key={dir.id}
                type="button"
                onClick={() => dir.isRoot ? handleSelectRoot(categoryId) : handleSelectDir(dir)}
                disabled={loading}
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '7px 10px',
                  border: 'none',
                  borderRadius: '7px',
                  backgroundColor: (selectedDirId === dir.id || selectedRootCategoryId === categoryId) ? '#eef2ff' : 'transparent',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  fontSize: '0.84rem',
                  fontWeight: 500,
                  color: dir.isRoot ? 'var(--primary)' : 'var(--text-secondary)',
                  textAlign: 'left',
                  fontFamily: 'inherit',
                  borderLeft: (selectedDirId === dir.id || selectedRootCategoryId === categoryId) ? '3px solid var(--primary)' : '3px solid transparent',
                  marginLeft: '-3px',
                }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill={dir.isRoot ? 'var(--primary)' : 'none'} stroke={dir.isRoot ? 'var(--primary)' : 'var(--text-tertiary)'} strokeWidth="2">
                  <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                </svg>
                <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {dir.name}
                </span>
                {(selectedDirId === dir.id || selectedRootCategoryId === categoryId) && (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" strokeWidth="2.5">
                    <polyline points="20 6 9 17 4 12"/>
                  </svg>
                )}
              </button>
            ))}
          </div>
        ))
      )}
      <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--border)' }}>
        <button
          type="button"
          onClick={onClose}
          disabled={loading}
          style={{ flex: 1, padding: '0.625rem', backgroundColor: 'var(--bg)', color: 'var(--text-secondary)', border: '1px solid var(--border-soft)', borderRadius: '0.5rem', fontSize: '0.875rem', fontWeight: 500, cursor: 'pointer', fontFamily: 'inherit' }}
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={handleConfirm}
          disabled={loading || (selectedDirId === null && selectedRootCategoryId === null)}
          style={{ flex: 1, padding: '0.625rem', backgroundColor: (selectedDirId === null && selectedRootCategoryId === null) ? 'var(--text-tertiary)' : 'var(--text)', color: 'var(--surface)', border: 'none', borderRadius: '0.5rem', fontSize: '0.875rem', fontWeight: 600, cursor: (selectedDirId === null && selectedRootCategoryId === null) ? 'not-allowed' : 'pointer', fontFamily: 'inherit', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
        >
          {loading ? (
            <>
              <span style={{ width: '14px', height: '14px', border: '2px solid rgba(255,255,255,0.3)', borderTopColor: 'var(--surface)', borderRadius: '50%', animation: 'spin 0.7s linear infinite', display: 'inline-block' }} />
              Moving…
            </>
          ) : (
            'Move'
          )}
        </button>
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}