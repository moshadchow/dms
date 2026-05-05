import { useEffect, useState, useCallback } from 'react'
import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
import { toast } from 'react-hot-toast'
import { directoriesApi } from '@/api/directories.api'
import { categoriesApi } from '@/api/categories.api'
import { documentsApi } from '@/api/documents.api'
import { useDirectoryStore } from '@/store/directoryStore'
import { usePermissions } from '@/hooks/usePermissions'
import DirectoryTree from '@/components/directories/DirectoryTree'
import DocumentCard from '@/components/documents/DocumentCard'
import DocumentViewer from '@/components/documents/DocumentViewer'
import UploadModal from '@/components/documents/UploadModal'
import EditDocumentModal from '@/components/documents/EditDocumentModal'
import type { Category } from '@/types/category.types'
import type { DirectoryNode } from '@/types/directory.types'
import type { Document, DocumentListResponse } from '@/types/document.types'
import { formatFileSize } from '@/utils/formatters'

export default function DocumentsPage() {
  const { directoryId } = useParams()
  const [searchParams]  = useSearchParams()
  const navigate        = useNavigate()
  const isRoot          = searchParams.get('root') === 'true'
  const { canCreate } = usePermissions()

  const { setSelectedCategory, setSelectedDirectory, refreshDirectories } = useDirectoryStore()

  // ── Page state ────────────────────────────────────────────────
  const [resolvedCategoryId, setResolvedCategoryId] = useState<number | null>(null)
  const [resolvedDirId, setResolvedDirId]           = useState<number | null>(null)
  const [category, setCategory]     = useState<Category | null>(null)
  const [tree, setTree]             = useState<DirectoryNode[]>([])
  const [loading, setLoading]       = useState(true)
  const [treeLoading, setTreeLoading] = useState(false)

  // ── Document state ────────────────────────────────────────────
  const [docData, setDocData]       = useState<DocumentListResponse | null>(null)
  const [docLoading, setDocLoading] = useState(false)
  const [search, setSearch]         = useState('')
  const [fileTypeFilter, setFileTypeFilter] = useState('')
  const [page, setPage]             = useState(1)
  const LIMIT = 20

  // ── Modal state ───────────────────────────────────────────────
  const [viewingDoc, setViewingDoc]   = useState<Document | null>(null)
  const [editingDoc, setEditingDoc]   = useState<Document | null>(null)
  const [uploadOpen, setUploadOpen]   = useState(false)

  // ── Resolve category/directory from URL ───────────────────────
  useEffect(() => {
    if (!directoryId) return
    setLoading(true)
    setResolvedCategoryId(null)
    setResolvedDirId(null)
    setTree([])
    setDocData(null)

    const run = async () => {
      try {
        if (isRoot) {
          const catId = parseInt(directoryId)
          const cat   = await categoriesApi.get(catId)
          setCategory(cat)
          setResolvedCategoryId(catId)
          setSelectedCategory(catId)
        } else {
          const dir = await directoriesApi.get(parseInt(directoryId))
          const cat = await categoriesApi.get(dir.category_id)
          setCategory(cat)
          setResolvedCategoryId(dir.category_id)
          setResolvedDirId(dir.id)
          setSelectedCategory(dir.category_id)
          setSelectedDirectory(dir.id)
        }
      } catch {
        toast.error('Failed to load page')
        navigate('/dashboard')
      } finally {
        setLoading(false)
      }
    }
    run()
  }, [directoryId, isRoot])

  // ── Load directory tree ───────────────────────────────────────
  const loadTree = useCallback(async (catId: number) => {
    setTreeLoading(true)
    try {
      const data = await directoriesApi.getTree(catId)
      setTree(data)
    } catch {
      toast.error('Failed to load directories')
    } finally {
      setTreeLoading(false)
    }
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

  // ── Load documents when directory or filters change ───────────
  const loadDocuments = useCallback(async () => {
    if (!resolvedDirId) return
    setDocLoading(true)
    try {
      const data = await documentsApi.list({
        directory_id: resolvedDirId,
        search:       search.trim() || undefined,
        file_type:    (fileTypeFilter || undefined) as any,
        skip:         (page - 1) * LIMIT,
        limit:        LIMIT,
      })
      setDocData(data)
    } catch {
      toast.error('Failed to load documents')
    } finally {
      setDocLoading(false)
    }
  }, [resolvedDirId, search, fileTypeFilter, page])

  useEffect(() => {
    if (resolvedDirId) loadDocuments()
    else setDocData(null)
  }, [resolvedDirId, loadDocuments])

  // Reset page when search/filter changes
  useEffect(() => { setPage(1) }, [search, fileTypeFilter, resolvedDirId])

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '300px' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ width: '28px', height: '28px', border: '3px solid #e2e8f0', borderTopColor: '#4f46e5', borderRadius: '50%', animation: 'spin 0.7s linear infinite', margin: '0 auto 0.75rem' }} />
          <p style={{ color: 'var(--text-tertiary)', fontSize: '0.875rem', margin: 0 }}>Loading…</p>
        </div>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    )
  }

  const totalPages = docData ? Math.ceil(docData.total / LIMIT) : 1

  return (
    <>
      <div style={{ display: 'flex', gap: '1.25rem', height: '100%', minHeight: 0 }}>

        {/* ── Left: directory tree ── */}
        <div style={{ width: '250px', flexShrink: 0, backgroundColor: 'var(--surface)', borderRadius: '1rem', border: '1px solid var(--border)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ padding: '0.875rem 1rem', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{ width: '28px', height: '28px', backgroundColor: 'var(--primary-soft)', borderRadius: '7px', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" strokeWidth="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
              </div>
              <div style={{ overflow: 'hidden' }}>
                <p style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text)', margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {category?.name ?? '…'}
                </p>
                <p style={{ fontSize: '0.68rem', color: 'var(--text-tertiary)', margin: '1px 0 0' }}>
                  {treeLoading ? 'Loading…' : `${tree.length} ${tree.length === 1 ? 'dir' : 'dirs'}`}
                </p>
              </div>
            </div>
          </div>
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {treeLoading ? (
              <div style={{ padding: '2rem', display: 'flex', justifyContent: 'center' }}>
                <div style={{ width: '20px', height: '20px', border: '2px solid #e2e8f0', borderTopColor: '#4f46e5', borderRadius: '50%', animation: 'spin 0.7s linear infinite' }} />
                <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
              </div>
            ) : resolvedCategoryId != null ? (
              <DirectoryTree
                categoryId={resolvedCategoryId}
                tree={tree}
                onRefresh={handleTreeRefresh}
              />
            ) : null}
          </div>
        </div>

        {/* ── Right: document panel ── */}
        <div style={{ flex: 1, backgroundColor: 'var(--surface)', borderRadius: '1rem', border: '1px solid var(--border)', display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>

          {resolvedDirId ? (
            <>
              {/* Document panel header */}
              <div style={{ padding: '0.875rem 1.25rem', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem', flexShrink: 0 }}>
                <div>
                  <p style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text)', margin: 0 }}>Documents</p>
                  <p style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', margin: '1px 0 0' }}>
                    {docData ? `${docData.total} file${docData.total !== 1 ? 's' : ''}` : '…'}
                  </p>
                </div>
                {canCreate && (
                  <button
                    onClick={() => setUploadOpen(true)}
                    style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '7px 14px', backgroundColor: 'var(--text)', color: 'var(--surface)', border: 'none', borderRadius: '8px', fontSize: '0.82rem', fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}
                  >
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                    Upload
                  </button>
                )}
              </div>

              {/* Search + filter bar */}
              <div style={{ padding: '0.75rem 1.25rem', borderBottom: '1px solid var(--border)', display: 'flex', gap: '0.625rem', flexShrink: 0 }}>
                <div style={{ flex: 1, position: 'relative' }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2" style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)' }}>
                    <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
                  </svg>
                  <input
                    className="input"
                    placeholder="Search documents…"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    style={{ paddingLeft: '32px', fontSize: '0.82rem' }}
                  />
                </div>
                <select
                  value={fileTypeFilter}
                  onChange={(e) => setFileTypeFilter(e.target.value)}
                  className="input"
                  style={{ width: '120px', fontSize: '0.82rem' }}
                >
                  <option value="">All types</option>
                  <option value="pdf">PDF</option>
                  <option value="excel">Excel</option>
                  <option value="image">Image</option>
                </select>
              </div>

              {/* Document grid */}
              <div style={{ flex: 1, overflowY: 'auto', padding: '1rem 1.25rem' }}>
                {docLoading ? (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '0.875rem' }}>
                    {[...Array(6)].map((_, i) => (
                      <div key={i} style={{ backgroundColor: 'var(--bg)', borderRadius: '0.875rem', border: '1px solid var(--border)', padding: '1rem', animation: 'pulse 1.5s ease infinite' }}>
                        <div style={{ width: '40px', height: '40px', backgroundColor: 'var(--surface-2)', borderRadius: '10px', marginBottom: '0.75rem' }} />
                        <div style={{ height: '13px', backgroundColor: 'var(--surface-2)', borderRadius: '4px', marginBottom: '6px', width: '80%' }} />
                        <div style={{ height: '10px', backgroundColor: 'var(--bg)', borderRadius: '4px', width: '55%' }} />
                        <style>{`@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.5}}`}</style>
                      </div>
                    ))}
                  </div>
                ) : !docData || docData.items.length === 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', textAlign: 'center', padding: '2rem' }}>
                    <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="#e2e8f0" strokeWidth="1.5" style={{ marginBottom: '1rem' }}>
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                      <polyline points="14 2 14 8 20 8"/>
                    </svg>
                    <p style={{ fontWeight: 600, color: 'var(--text-tertiary)', margin: 0 }}>
                      {search || fileTypeFilter ? 'No documents match your filters' : 'No documents yet'}
                    </p>
                    {canCreate && !search && !fileTypeFilter && (
                      <button
                        onClick={() => setUploadOpen(true)}
                        style={{ marginTop: '0.75rem', padding: '7px 16px', backgroundColor: 'var(--text)', color: 'var(--surface)', border: 'none', borderRadius: '8px', fontSize: '0.82rem', fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}
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
                        />
                      ))}
                    </div>

                    {/* Pagination */}
                    {totalPages > 1 && (
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', marginTop: '1.25rem', paddingTop: '1rem', borderTop: '1px solid var(--border)' }}>
                        <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1} style={pageBtn}>←</button>
                        <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>Page {page} of {totalPages}</span>
                        <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page === totalPages} style={pageBtn}>→</button>
                      </div>
                    )}
                  </>
                )}
              </div>
            </>
          ) : (
            /* No directory selected */
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '2rem', textAlign: 'center' }}>
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#e2e8f0" strokeWidth="1.5" style={{ marginBottom: '1rem' }}>
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

      {/* ── Modals ── */}
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

const pageBtn: React.CSSProperties = {
  padding: '5px 12px', borderRadius: '7px', border: '1px solid var(--border-soft)',
  backgroundColor: 'var(--surface)', color: 'var(--text-secondary)', fontSize: '0.82rem',
  cursor: 'pointer', fontFamily: 'inherit',
}
