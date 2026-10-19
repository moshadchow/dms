import { useEffect, useState, useCallback } from 'react'
import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
import { toast } from 'react-hot-toast'
import { isAccessDeniedError } from '@/api/client'
import { directoriesApi } from '@/api/directories.api'
import { categoriesApi } from '@/api/categories.api'
import { documentsApi } from '@/api/documents.api'
import { usersApi } from '@/api/users.api'
import { useCategoryAccess } from '@/hooks/useCategoryAccess'
import { useDirectoryStore } from '@/store/directoryStore'
import { usePermissions } from '@/hooks/usePermissions'
import DirectoryTree from '@/components/directories/DirectoryTree'
import DocumentCard from '@/components/documents/DocumentCard'
import DocumentViewer from '@/components/documents/DocumentViewer'
import UploadModal from '@/components/documents/UploadModal'
import EditDocumentModal from '@/components/documents/EditDocumentModal'
import type { Category } from '@/types/category.types'
import type { DirectoryNode } from '@/types/directory.types'
import type { Document, DocumentListResponse, FileType, SortField, SortOrder, User } from '@/types/document.types'

export default function DocumentsPage() {
  const { directoryId } = useParams()
  const [searchParams]  = useSearchParams()
  const navigate        = useNavigate()
  const isRoot          = searchParams.get('root') === 'true'
  const isGlobalSearch  = !directoryId // Global search mode when no directoryId in URL
  const { canCreate } = usePermissions()
  const { isAdmin, canAccessCategory } = useCategoryAccess()

  const { setSelectedCategory, setSelectedDirectory, refreshDirectories } = useDirectoryStore()

  // Page state
  const [resolvedCategoryId, setResolvedCategoryId] = useState<number | null>(null)
  const [resolvedDirId, setResolvedDirId]           = useState<number | null>(null)
  const [navOnly, setNavOnly]                       = useState(false)
  const [category, setCategory]     = useState<Category | null>(null)
  const [tree, setTree]             = useState<DirectoryNode[]>([])
  const [loading, setLoading]       = useState(true)
  const [treeLoading, setTreeLoading] = useState(false)

  // Document state
  const [docData, setDocData]       = useState<DocumentListResponse | null>(null)
  const [docLoading, setDocLoading] = useState(false)
  const [search, setSearch]         = useState('')
  const [fileTypeFilter, setFileTypeFilter] = useState<FileType | ''>('')
  const [showArchived, setShowArchived]     = useState(false)
  const [selectedIds, setSelectedIds]       = useState<Set<number>>(new Set())
  const [bulkRestoring, setBulkRestoring]   = useState(false)
  const [page, setPage]             = useState(1)
  const LIMIT = 20

  // Sorting & Advanced Filtering state
  const [sortBy, setSortBy]         = useState<SortField>('created_at')
  const [sortOrder, setSortOrder]   = useState<SortOrder>('desc')
  const [uploadedBy, setUploadedBy] = useState<number | ''>('')
  const [createdFrom, setCreatedFrom] = useState('')
  const [createdTo, setCreatedTo]     = useState('')
  const [updatedFrom, setUpdatedFrom] = useState('')
  const [updatedTo, setUpdatedTo]     = useState('')
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false)
  const [users, setUsers]           = useState<User[]>([])
  const [usersLoading, setUsersLoading] = useState(false)

  // Fetch users for "uploaded by" filter
  useEffect(() => {
    if (isAdmin) {
      Promise.resolve().then(() => setUsersLoading(true))
      usersApi.list({ limit: 500 })
        .then((data) => setUsers(data.items))
        .catch(() => toast.error('Failed to load users'))
        .finally(() => setUsersLoading(false))
    }
  }, [isAdmin])

  // Modal state
  const [viewingDoc, setViewingDoc]   = useState<Document | null>(null)
  const [editingDoc, setEditingDoc]   = useState<Document | null>(null)
  const [uploadOpen, setUploadOpen]   = useState(false)

  // Resolve category/directory from URL
  useEffect(() => {
    // Global search mode: no directoryId in URL, skip directory resolution
    if (isGlobalSearch) {
      Promise.resolve()
        .then(() => {
          setLoading(true)
          setResolvedCategoryId(null)
          setResolvedDirId(null)
          setNavOnly(false)
          setTree([])
          setDocData(null)
        })
        .finally(() => setLoading(false))
      return
    }

    if (!directoryId) return

    const run = async () => {
      try {
        if (isRoot) {
          const catId = parseInt(directoryId)
          if (Number.isNaN(catId)) {
            navigate('/dashboard', { replace: true })
            return
          }

          if (!isAdmin && !canAccessCategory(catId)) {
            navigate('/forbidden', { replace: true })
            return
          }

          const cat   = await categoriesApi.get(catId)
          setCategory(cat)
          setResolvedCategoryId(catId)
          setNavOnly(false)
          setSelectedCategory(catId)
        } else {
          const dir = await directoriesApi.get(parseInt(directoryId))
          const cat = await categoriesApi.get(dir.category_id)
          setCategory(cat)
          setResolvedCategoryId(dir.category_id)
          setResolvedDirId(dir.id)
          setNavOnly(dir.navigation_only ?? false)
          setSelectedCategory(dir.category_id)
          setSelectedDirectory(dir.id)
        }
      } catch (error) {
        if (!isAdmin && isAccessDeniedError(error)) {
          navigate('/forbidden', { replace: true })
          return
        }

        toast.error('Failed to load page')
        navigate('/dashboard', { replace: true })
      } finally {
        setLoading(false)
      }
    }

    Promise.resolve()
      .then(() => {
        setLoading(true)
        setResolvedCategoryId(null)
        setResolvedDirId(null)
        setNavOnly(false)
        setTree([])
        setDocData(null)
        return run()
      })
  }, [directoryId, isRoot, isGlobalSearch, isAdmin, canAccessCategory, navigate, setSelectedCategory, setSelectedDirectory])

  // Load directory tree
  const loadTree = useCallback((catId: number) => {
    Promise.resolve()
      .then(() => {
        setTreeLoading(true)
        return directoriesApi.getTree(catId)
      })
      .then((data) => {
        setTree(data)
      })
      .catch(() => {
        toast.error('Failed to load directories')
      })
      .finally(() => {
        setTreeLoading(false)
      })
  }, [])

  useEffect(() => {
    if (resolvedCategoryId) loadTree(resolvedCategoryId)
  }, [resolvedCategoryId, loadTree])

  const handleTreeRefresh = useCallback(() => {
    if (resolvedCategoryId) {
      loadTree(resolvedCategoryId)
      refreshDirectories()
    }
  }, [resolvedCategoryId, loadTree, refreshDirectories])

  // Load documents when directory or filters change
  const loadDocuments = useCallback(() => {
    // In global search mode, we don't need resolvedDirId
    // For regular mode, we need resolvedDirId
    if (!isGlobalSearch && !resolvedDirId) return
    Promise.resolve()
      .then(() => {
        setDocLoading(true)
        setSelectedIds(new Set())
        return documentsApi.list({
          directory_id: resolvedDirId ?? undefined, // undefined for global search
          search:       search.trim() || undefined,
          file_type:    fileTypeFilter || undefined,
          status:       showArchived ? 'archived' : undefined,
          sort_by:      sortBy,
          sort_order:   sortOrder,
          uploaded_by:  uploadedBy || undefined,
          created_from: createdFrom || undefined,
          created_to:   createdTo || undefined,
          updated_from: updatedFrom || undefined,
          updated_to:   updatedTo || undefined,
          skip:         (page - 1) * LIMIT,
          limit:        LIMIT,
        })
      })
      .then((data) => {
        setDocData(data)
      })
      .catch(() => {
        toast.error('Failed to load documents')
      })
      .finally(() => {
        setDocLoading(false)
      })
  }, [isGlobalSearch, resolvedDirId, search, fileTypeFilter, showArchived, sortBy, sortOrder, uploadedBy, createdFrom, createdTo, updatedFrom, updatedTo, page])

  const handleSelectDoc = useCallback((id: number, checked: boolean) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (checked) {
        next.add(id)
      } else {
        next.delete(id)
      }
      return next
    })
  }, [])

  const handleBulkRestore = async () => {
    if (selectedIds.size === 0) return
    setBulkRestoring(true)
    try {
      const result = await documentsApi.bulkRestore([...selectedIds])
      if (result.restored.length > 0)
        toast.success('Restored ' + result.restored.length + ' document' + (result.restored.length > 1 ? 's' : ''))
      if (result.failed.length > 0)
        toast.error(result.failed.length + ' document' + (result.failed.length > 1 ? 's' : '') + ' could not be restored')
      loadDocuments()
    } catch {
      toast.error('Bulk restore failed')
    } finally {
      setBulkRestoring(false)
    }
  }

  useEffect(() => {
    if (isGlobalSearch) {
      loadDocuments()
    } else if (resolvedDirId) {
      loadDocuments()
    } else {
      Promise.resolve().then(() => setDocData(null))
    }
  }, [resolvedDirId, isGlobalSearch, loadDocuments])

  // Reset page when search/filter/status changes (adjusted during render)
  const docFilterKey = search + '|' + fileTypeFilter + '|' + String(showArchived) + '|' + sortBy + '|' + sortOrder + '|' + uploadedBy + '|' + createdFrom + '|' + createdTo + '|' + updatedFrom + '|' + updatedTo + '|' + (resolvedDirId ?? '') + '|' + String(isGlobalSearch)
  const [prevDocFilterKey, setPrevDocFilterKey] = useState(docFilterKey)
  if (prevDocFilterKey !== docFilterKey) {
    setPrevDocFilterKey(docFilterKey)
    setPage(1)
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '300px' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ width: '28px', height: '28px', border: '3px solid var(--border-soft)', borderTopColor: 'var(--primary)', borderRadius: '50%', animation: 'spin 0.7s linear infinite', margin: '0 auto 0.75rem' }} />
          <p style={{ color: 'var(--text-tertiary)', fontSize: '0.875rem', margin: 0 }}>Loading...</p>
        </div>
      </div>
    )
  }

  const totalPages = docData ? Math.ceil(docData.total / LIMIT) : 1

  // Sort options
  const sortFields = [
    { value: 'created_at' as SortField, label: 'Created date' },
    { value: 'updated_at' as SortField, label: 'Updated date' },
    { value: 'title' as SortField, label: 'Title' },
    { value: 'file_name' as SortField, label: 'File name' },
    { value: 'file_size' as SortField, label: 'File size' },
  ]

  return (
    <>
      <div style={{ display: 'flex', gap: '1.25rem', height: '100%', minHeight: 0 }}>

        {/* Left: directory tree */}
        <div style={{ width: '250px', flexShrink: 0, backgroundColor: 'var(--surface)', borderRadius: '1rem', border: '1px solid var(--border)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ padding: '0.875rem 1rem', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{ width: '28px', height: '28px', backgroundColor: 'var(--primary-soft)', borderRadius: '7px', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" strokeWidth="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
              </div>
              <div style={{ overflow: 'hidden' }}>
                <p style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text)', margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {isGlobalSearch ? 'All Categories' : (category?.name ?? '...')}
                </p>
                <p style={{ fontSize: '0.68rem', color: 'var(--text-tertiary)', margin: '1px 0 0' }}>
                  {treeLoading ? 'Loading...' : tree.length + ' ' + (tree.length === 1 ? 'dir' : 'dirs')}
                </p>
              </div>
            </div>
          </div>
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {treeLoading ? (
              <div style={{ padding: '2rem', display: 'flex', justifyContent: 'center' }}>
                <div style={{ width: '20px', height: '20px', border: '2px solid var(--border-soft)', borderTopColor: 'var(--primary)', borderRadius: '50%', animation: 'spin 0.7s linear infinite' }} />
              </div>
            ) : resolvedCategoryId != null ? (
              <DirectoryTree
                categoryId={resolvedCategoryId}
                tree={tree}
                onRefresh={handleTreeRefresh}
              />
            ) : isGlobalSearch ? (
              <div style={{ padding: '1rem', color: 'var(--text-tertiary)', fontSize: '0.8rem', textAlign: 'center' }}>
                Select a category to browse directories
              </div>
            ) : null}
          </div>
        </div>

        {/* Right: document panel */}
        <div style={{ flex: 1, backgroundColor: 'var(--surface)', borderRadius: '1rem', border: '1px solid var(--border)', display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>

          {resolvedDirId ? (
            <>
              {/* Document panel header */}
              <div style={{ padding: '0.875rem 1.25rem', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem', flexShrink: 0 }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <p style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text)', margin: 0 }}>Documents</p>
                    {navOnly && (
                      <span style={{ fontSize: '0.62rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-tertiary)', backgroundColor: 'var(--surface-2)', border: '1px solid var(--border-soft)', padding: '2px 8px', borderRadius: '999px' }}>
                        View only
                      </span>
                    )}
                  </div>
                  <p style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', margin: '1px 0 0' }}>
                    {docData ? docData.total + ' file' + (docData.total !== 1 ? 's' : '') : '...'}
                  </p>
                </div>
                {canCreate && !navOnly && (
                  <button
                    className="btn btn-primary"
                    onClick={() => setUploadOpen(true)}
                  >
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                    Upload
                  </button>
                )}
              </div>

              {/* Search + filter bar */}
              <div style={{ padding: '0.75rem 1.25rem', borderBottom: '1px solid var(--border)', display: 'flex', gap: '0.625rem', flexShrink: 0, flexWrap: 'wrap', alignItems: 'center' }}>
                <div style={{ flex: 1, position: 'relative', minWidth: '140px' }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2" style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)' }}>
                    <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
                  </svg>
                  <input
                    className="input"
                    placeholder="Search documents..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    style={{ paddingLeft: '32px', fontSize: '0.82rem' }}
                  />
                </div>
                <select
                  value={fileTypeFilter}
                  onChange={(e) => setFileTypeFilter(e.target.value as FileType | '')}
                  className="input"
                  style={{ width: '120px', fontSize: '0.82rem' }}
                >
                  <option value="">All types</option>
                  <option value="pdf">PDF</option>
                  <option value="docx">DOCX</option>
                  <option value="excel">Excel</option>
                  <option value="image">Image</option>
                </select>

                {/* Sort dropdown */}
                <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
                  <select
                    value={sortBy}
                    onChange={(e) => setSortBy(e.target.value as SortField)}
                    className="input"
                    style={{ width: '140px', fontSize: '0.82rem' }}
                  >
                    {sortFields.map((f) => (
                      <option key={f.value} value={f.value}>{f.label}</option>
                    ))}
                  </select>
                  <select
                    value={sortOrder}
                    onChange={(e) => setSortOrder(e.target.value as SortOrder)}
                    className="input"
                    style={{ width: '80px', fontSize: '0.82rem' }}
                  >
                    <option value="asc">Ascending</option>
                    <option value="desc">Descending</option>
                  </select>
                </div>

                {/* Advanced filters toggle */}
                <button
                  type="button"
                  onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
                  className="btn btn-secondary"
                  style={{ fontSize: '0.82rem', padding: '5px 12px' }}
                >
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: '4px' }}>
                    <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>
                  </svg>
                  Filters
                </button>

                {isAdmin && (
                  <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.82rem', color: 'var(--text-secondary)', cursor: 'pointer', whiteSpace: 'nowrap', userSelect: 'none' }}>
                    <input
                      type="checkbox"
                      checked={showArchived}
                      onChange={(e) => { setShowArchived(e.target.checked); setSelectedIds(new Set()) }}
                      style={{ cursor: 'pointer' }}
                    />
                    Show Archived
                  </label>
                )}
              </div>

              {/* Advanced filters panel */}
              {showAdvancedFilters && (
                <div style={{ padding: '0.75rem 1.25rem', borderBottom: '1px solid var(--border)', backgroundColor: 'var(--bg)', display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center' }}>
                  {/* Uploaded by */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Uploaded by</label>
                    <select
                      value={uploadedBy}
                      onChange={(e) => setUploadedBy(e.target.value ? parseInt(e.target.value) : '')}
                      className="input"
                      style={{ width: '180px', fontSize: '0.82rem' }}
                      disabled={usersLoading}
                    >
                      <option value="">All users</option>
                      {users.map((u) => (
                        <option key={u.id} value={u.id}>{u.full_name} ({u.email})</option>
                      ))}
                    </select>
                  </div>

                  {/* Created date range */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Created</label>
                    <input type="date" value={createdFrom} onChange={(e) => setCreatedFrom(e.target.value)} className="input" style={{ width: '140px', fontSize: '0.82rem' }} />
                    <span style={{ color: 'var(--text-tertiary)', fontSize: '0.75rem' }}>to</span>
                    <input type="date" value={createdTo} onChange={(e) => setCreatedTo(e.target.value)} className="input" style={{ width: '140px', fontSize: '0.82rem' }} />
                  </div>

                  {/* Updated date range */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Updated</label>
                    <input type="date" value={updatedFrom} onChange={(e) => setUpdatedFrom(e.target.value)} className="input" style={{ width: '140px', fontSize: '0.82rem' }} />
                    <span style={{ color: 'var(--text-tertiary)', fontSize: '0.75rem' }}>to</span>
                    <input type="date" value={updatedTo} onChange={(e) => setUpdatedTo(e.target.value)} className="input" style={{ width: '140px', fontSize: '0.82rem' }} />
                  </div>

                  {/* Clear filters button */}
                  <button
                    type="button"
                    onClick={() => {
                      setUploadedBy('')
                      setCreatedFrom('')
                      setCreatedTo('')
                      setUpdatedFrom('')
                      setUpdatedTo('')
                    }}
                    className="btn btn-ghost"
                    style={{ fontSize: '0.82rem', marginLeft: 'auto', padding: '5px 12px' }}
                  >
                    Clear filters
                  </button>
                </div>
              )}

              {/* Bulk restore action bar */}
              {showArchived && selectedIds.size > 0 && (
                <div style={{ padding: '0.6rem 1.25rem', backgroundColor: 'var(--info-bg)', borderBottom: '1px solid var(--info)', display: 'flex', alignItems: 'center', gap: '0.75rem', flexShrink: 0 }}>
                  <span style={{ fontSize: '0.82rem', color: 'var(--info)', fontWeight: 500 }}>
                    {selectedIds.size} selected
                  </span>
                  <button
                    onClick={handleBulkRestore}
                    disabled={bulkRestoring}
                    style={{ display: 'flex', alignItems: 'center', gap: '5px', padding: '5px 14px', backgroundColor: 'var(--info)', color: '#fff', border: 'none', borderRadius: '7px', fontSize: '0.82rem', fontWeight: 600, cursor: bulkRestoring ? 'not-allowed' : 'pointer', fontFamily: 'inherit', opacity: bulkRestoring ? 0.7 : 1 }}
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-4.5"/></svg>
                    {bulkRestoring ? 'Restoring...' : 'Restore Selected'}
                  </button>
                  <button
                    onClick={() => setSelectedIds(new Set())}
                    style={{ padding: '5px 10px', backgroundColor: 'transparent', color: 'var(--text-secondary)', border: '1px solid var(--border-soft)', borderRadius: '7px', fontSize: '0.82rem', cursor: 'pointer', fontFamily: 'inherit' }}
                  >
                    Clear
                  </button>
                </div>
              )}

              {/* Document grid */}
              <div style={{ flex: 1, overflowY: 'auto', padding: '1rem 1.25rem' }}>
                {docLoading ? (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '0.875rem' }} aria-busy="true" role="status">
                    <span className="sr-only">Loading documents...</span>
                    {[...Array(6)].map((_, i) => (
                      <div key={i} style={{ backgroundColor: 'var(--bg)', borderRadius: '0.875rem', border: '1px solid var(--border)', padding: '1rem', animation: 'pulse 1.5s ease infinite' }}>
                        <div style={{ width: '40px', height: '40px', backgroundColor: 'var(--surface-2)', borderRadius: '10px', marginBottom: '0.75rem' }} />
                        <div style={{ height: '13px', backgroundColor: 'var(--surface-2)', borderRadius: '4px', marginBottom: '6px', width: '80%' }} />
                        <div style={{ height: '10px', backgroundColor: 'var(--bg)', borderRadius: '4px', width: '55%' }} />
                      </div>
                    ))}
                  </div>
                ) : !docData || docData.items.length === 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', textAlign: 'center', padding: '2rem' }}>
                    <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="1.5" style={{ marginBottom: '1rem' }}>
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                      <polyline points="14 2 14 8 20 8"/>
                    </svg>
                    <p style={{ fontWeight: 600, color: 'var(--text-tertiary)', margin: 0 }}>
                      {showArchived ? 'No archived documents in this directory' : search || fileTypeFilter || uploadedBy || createdFrom || createdTo || updatedFrom || updatedTo ? 'No documents match your filters' : navOnly ? 'Navigation folder - open a subfolder to view its documents' : 'No documents yet'}
                    </p>
                    {canCreate && !navOnly && !search && !fileTypeFilter && (
                      <button
                        className="btn btn-primary"
                        onClick={() => setUploadOpen(true)}
                        style={{ marginTop: '0.75rem' }}
                      >
                        Upload first document
                      </button>
                    )}
                  </div>
                ) : (
                  <>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '0.875rem' }}>
                      {docData.items.map((doc) => (
                        <DocumentCard
                          key={doc.id}
                          doc={doc}
                          onView={setViewingDoc}
                          onRefresh={loadDocuments}
                          selectable={showArchived && isAdmin}
                          selected={selectedIds.has(doc.id)}
                          onSelect={handleSelectDoc}
                        />
                      ))}
                    </div>

                    {/* Pagination */}
                    {totalPages > 1 && (
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', marginTop: '1.25rem', paddingTop: '1rem', borderTop: '1px solid var(--border)' }}>
                        <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1} style={pageBtn}>&larr;</button>
                        <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>Page {page} of {totalPages}</span>
                        <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page === totalPages} style={pageBtn}>&rarr;</button>
                      </div>
                    )}
                  </>
                )}
              </div>
            </>
          ) : isGlobalSearch ? (
            /* Global search mode */
            <>
              {/* Document panel header */}
              <div style={{ padding: '0.875rem 1.25rem', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem', flexShrink: 0 }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <p style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text)', margin: 0 }}>Global Search</p>
                    <span style={{ fontSize: '0.62rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--primary)', backgroundColor: 'var(--primary-soft)', border: '1px solid var(--primary-border)', padding: '2px 8px', borderRadius: '999px' }}>
                      All accessible directories
                    </span>
                  </div>
                  <p style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', margin: '1px 0 0' }}>
                    {docData ? docData.total + ' file' + (docData.total !== 1 ? 's' : '') : '...'}
                  </p>
                </div>
              </div>

              {/* Search + filter bar */}
              <div style={{ padding: '0.75rem 1.25rem', borderBottom: '1px solid var(--border)', display: 'flex', gap: '0.625rem', flexShrink: 0, flexWrap: 'wrap', alignItems: 'center' }}>
                <div style={{ flex: 1, position: 'relative', minWidth: '140px' }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2" style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)' }}>
                    <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
                  </svg>
                  <input
                    className="input"
                    placeholder="Search across all accessible documents..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    style={{ paddingLeft: '32px', fontSize: '0.82rem' }}
                  />
                </div>
                <select
                  value={fileTypeFilter}
                  onChange={(e) => setFileTypeFilter(e.target.value as FileType | '')}
                  className="input"
                  style={{ width: '120px', fontSize: '0.82rem' }}
                >
                  <option value="">All types</option>
                  <option value="pdf">PDF</option>
                  <option value="docx">DOCX</option>
                  <option value="excel">Excel</option>
                  <option value="image">Image</option>
                </select>

                {/* Sort dropdown */}
                <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
                  <select
                    value={sortBy}
                    onChange={(e) => setSortBy(e.target.value as SortField)}
                    className="input"
                    style={{ width: '140px', fontSize: '0.82rem' }}
                  >
                    {sortFields.map((f) => (
                      <option key={f.value} value={f.value}>{f.label}</option>
                    ))}
                  </select>
                  <select
                    value={sortOrder}
                    onChange={(e) => setSortOrder(e.target.value as SortOrder)}
                    className="input"
                    style={{ width: '80px', fontSize: '0.82rem' }}
                  >
                    <option value="asc">Ascending</option>
                    <option value="desc">Descending</option>
                  </select>
                </div>

                {/* Advanced filters toggle */}
                <button
                  type="button"
                  onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
                  className="btn btn-secondary"
                  style={{ fontSize: '0.82rem', padding: '5px 12px' }}
                >
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: '4px' }}>
                    <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>
                  </svg>
                  Filters
                </button>

                {isAdmin && (
                  <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.82rem', color: 'var(--text-secondary)', cursor: 'pointer', whiteSpace: 'nowrap', userSelect: 'none' }}>
                    <input
                      type="checkbox"
                      checked={showArchived}
                      onChange={(e) => { setShowArchived(e.target.checked); setSelectedIds(new Set()) }}
                      style={{ cursor: 'pointer' }}
                    />
                    Show Archived
                  </label>
                )}
              </div>

              {/* Advanced filters panel */}
              {showAdvancedFilters && (
                <div style={{ padding: '0.75rem 1.25rem', borderBottom: '1px solid var(--border)', backgroundColor: 'var(--bg)', display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center' }}>
                  {/* Uploaded by */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Uploaded by</label>
                    <select
                      value={uploadedBy}
                      onChange={(e) => setUploadedBy(e.target.value ? parseInt(e.target.value) : '')}
                      className="input"
                      style={{ width: '180px', fontSize: '0.82rem' }}
                      disabled={usersLoading}
                    >
                      <option value="">All users</option>
                      {users.map((u) => (
                        <option key={u.id} value={u.id}>{u.full_name} ({u.email})</option>
                      ))}
                    </select>
                  </div>

                  {/* Created date range */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Created</label>
                    <input type="date" value={createdFrom} onChange={(e) => setCreatedFrom(e.target.value)} className="input" style={{ width: '140px', fontSize: '0.82rem' }} />
                    <span style={{ color: 'var(--text-tertiary)', fontSize: '0.75rem' }}>to</span>
                    <input type="date" value={createdTo} onChange={(e) => setCreatedTo(e.target.value)} className="input" style={{ width: '140px', fontSize: '0.82rem' }} />
                  </div>

                  {/* Updated date range */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Updated</label>
                    <input type="date" value={updatedFrom} onChange={(e) => setUpdatedFrom(e.target.value)} className="input" style={{ width: '140px', fontSize: '0.82rem' }} />
                    <span style={{ color: 'var(--text-tertiary)', fontSize: '0.75rem' }}>to</span>
                    <input type="date" value={updatedTo} onChange={(e) => setUpdatedTo(e.target.value)} className="input" style={{ width: '140px', fontSize: '0.82rem' }} />
                  </div>

                  {/* Clear filters button */}
                  <button
                    type="button"
                    onClick={() => {
                      setUploadedBy('')
                      setCreatedFrom('')
                      setCreatedTo('')
                      setUpdatedFrom('')
                      setUpdatedTo('')
                    }}
                    className="btn btn-ghost"
                    style={{ fontSize: '0.82rem', marginLeft: 'auto', padding: '5px 12px' }}
                  >
                    Clear filters
                  </button>
                </div>
              )}

              {/* Document grid */}
              <div style={{ flex: 1, overflowY: 'auto', padding: '1rem 1.25rem' }}>
                {docLoading ? (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '0.875rem' }} aria-busy="true" role="status">
                    <span className="sr-only">Loading documents...</span>
                    {[...Array(6)].map((_, i) => (
                      <div key={i} style={{ backgroundColor: 'var(--bg)', borderRadius: '0.875rem', border: '1px solid var(--border)', padding: '1rem', animation: 'pulse 1.5s ease infinite' }}>
                        <div style={{ width: '40px', height: '40px', backgroundColor: 'var(--surface-2)', borderRadius: '10px', marginBottom: '0.75rem' }} />
                        <div style={{ height: '13px', backgroundColor: 'var(--surface-2)', borderRadius: '4px', marginBottom: '6px', width: '80%' }} />
                        <div style={{ height: '10px', backgroundColor: 'var(--bg)', borderRadius: '4px', width: '55%' }} />
                      </div>
                    ))}
                  </div>
                ) : !docData || docData.items.length === 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', textAlign: 'center', padding: '2rem' }}>
                    <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="1.5" style={{ marginBottom: '1rem' }}>
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                      <polyline points="14 2 14 8 20 8"/>
                    </svg>
                    <p style={{ fontWeight: 600, color: 'var(--text-tertiary)', margin: 0 }}>
                      {search || fileTypeFilter || uploadedBy || createdFrom || createdTo || updatedFrom || updatedTo ? 'No documents match your filters' : 'No documents found across accessible directories'}
                    </p>
                  </div>
                ) : (
                  <>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '0.875rem' }}>
                      {docData.items.map((doc) => (
                        <DocumentCard
                          key={doc.id}
                          doc={doc}
                          onView={setViewingDoc}
                          onRefresh={loadDocuments}
                          selectable={showArchived && isAdmin}
                          selected={selectedIds.has(doc.id)}
                          onSelect={handleSelectDoc}
                        />
                      ))}
                    </div>

                    {/* Pagination */}
                    {totalPages > 1 && (
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', marginTop: '1.25rem', paddingTop: '1rem', borderTop: '1px solid var(--border)' }}>
                        <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1} style={pageBtn}>&larr;</button>
                        <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>Page {page} of {totalPages}</span>
                        <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page === totalPages} style={pageBtn}>&rarr;</button>
                      </div>
                    )}
                  </>
                )}
              </div>
            </>
          ) : (
            /* No directory selected */
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '2rem', textAlign: 'center' }}>
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="1.5" style={{ marginBottom: '1rem' }}>
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
              </svg>
              <p style={{ fontWeight: 600, color: 'var(--text-tertiary)', margin: 0, fontSize: '0.95rem' }}>Select a directory</p>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem', margin: '6px 0 0' }}>
                Click a directory in the left panel to view its documents
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Modals */}
      <DocumentViewer doc={viewingDoc} onClose={() => setViewingDoc(null)} />

      <UploadModal
        isOpen={uploadOpen}
        onClose={() => setUploadOpen(false)}
        directoryId={resolvedDirId ?? 0}
        onSuccess={() => { setUploadOpen(false); loadDocuments() }}
      />

      <EditDocumentModal
        isOpen={!!editingDoc}
        doc={editingDoc}
        onClose={() => setEditingDoc(null)}
        onSuccess={loadDocuments}
      />
    </>
  )
}

const pageBtn = {
  padding: '5px 12px', borderRadius: '7px', border: '1px solid var(--border-soft)',
  backgroundColor: 'var(--surface)', color: 'var(--text-secondary)', fontSize: '0.82rem',
  cursor: 'pointer', fontFamily: 'inherit',
}