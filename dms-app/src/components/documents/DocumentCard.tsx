import { useState } from 'react'
import { toast } from 'react-hot-toast'
import { documentsApi } from '@/api/documents.api'
import { getErrorMessage } from '@/api/client'
import { usePermissions } from '@/hooks/usePermissions'
import { formatFileSize, formatDateTime } from '@/utils/formatters'
import type { Document } from '@/types/document.types'

interface Props {
  doc:       Document
  onView:    (doc: Document) => void
  onRefresh: () => void
}

const FILE_ICONS: Record<string, React.ReactNode> = {
  pdf: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
      <polyline points="14 2 14 8 20 8"/>
      <line x1="16" y1="13" x2="8" y2="13"/>
      <line x1="16" y1="17" x2="8" y2="17"/>
    </svg>
  ),
  excel: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
      <polyline points="14 2 14 8 20 8"/>
      <line x1="8" y1="13" x2="16" y2="17"/>
      <line x1="16" y1="13" x2="8" y2="17"/>
    </svg>
  ),
  image: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#8b5cf6" strokeWidth="2">
      <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
      <circle cx="8.5" cy="8.5" r="1.5"/>
      <polyline points="21 15 16 10 5 21"/>
    </svg>
  ),
}

const FILE_BG: Record<string, string> = {
  pdf:   '#fef2f2',
  excel: '#f0fdf4',
  image: '#faf5ff',
}

const STATUS_STYLE: Record<string, { bg: string; color: string; label: string }> = {
  active:   { bg: '#f0fdf4', color: '#16a34a', label: 'Active' },
  archived: { bg: '#fefce8', color: '#ca8a04', label: 'Archived' },
  deleted:  { bg: '#fef2f2', color: '#dc2626', label: 'Deleted' },
}

export default function DocumentCard({ doc, onView, onRefresh }: Props) {
  const { canUpdate, canDelete, canDownload, isAdmin } = usePermissions()
  const [menuOpen, setMenuOpen]   = useState(false)
  const [loading, setLoading]     = useState(false)

  const statusStyle = STATUS_STYLE[doc.status] ?? STATUS_STYLE.active
  const fileIcon    = FILE_ICONS[doc.file_type]
  const fileBg      = FILE_BG[doc.file_type] ?? 'var(--bg)'

  const handleDownload = async () => {
    try {
      setLoading(true)
      await documentsApi.download(doc.id, doc.file_name)
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  const handleArchive = async () => {
    setMenuOpen(false)
    try {
      await documentsApi.archive(doc.id)
      toast.success('Document archived')
      onRefresh()
    } catch (err) {
      toast.error(getErrorMessage(err))
    }
  }

  const handleRestore = async () => {
    setMenuOpen(false)
    try {
      await documentsApi.restore(doc.id)
      toast.success('Document restored')
      onRefresh()
    } catch (err) {
      toast.error(getErrorMessage(err))
    }
  }

  const handleDelete = async () => {
    setMenuOpen(false)
    if (!confirm(`Delete "${doc.title}"? This cannot be undone.`)) return
    try {
      await documentsApi.delete(doc.id)
      toast.success('Document deleted')
      onRefresh()
    } catch (err) {
      toast.error(getErrorMessage(err))
    }
  }

  return (
    <div style={{
      backgroundColor: 'var(--surface)',
      borderRadius: '0.875rem',
      border: '1px solid var(--border)',
      padding: '1rem',
      display: 'flex',
      flexDirection: 'column',
      gap: '0.75rem',
      transition: 'box-shadow 150ms',
      position: 'relative',
    }}
      onMouseEnter={(e) => (e.currentTarget.style.boxShadow = '0 4px 16px rgba(0,0,0,0.07)')}
      onMouseLeave={(e) => (e.currentTarget.style.boxShadow = 'none')}
    >
      {/* Top row — icon + title + menu */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem' }}>
        {/* File type icon */}
        <div style={{ width: '40px', height: '40px', borderRadius: '10px', backgroundColor: fileBg, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
          {fileIcon}
        </div>

        {/* Title + filename */}
        <div style={{ flex: 1, overflow: 'hidden' }}>
          <p
            onClick={() => onView(doc)}
            style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text)', margin: 0, cursor: 'pointer', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
            title={doc.title}
          >
            {doc.title}
          </p>
          <p style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', margin: '2px 0 0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {doc.file_name}
          </p>
        </div>

        {/* Actions menu */}
        <div style={{ position: 'relative', flexShrink: 0 }}>
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            style={{ width: '28px', height: '28px', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '6px', border: 'none', backgroundColor: menuOpen ? 'var(--surface-2)' : 'transparent', cursor: 'pointer', color: 'var(--text-tertiary)' }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="5" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="12" cy="19" r="1.5"/></svg>
          </button>

          {menuOpen && (
            <>
              <div style={{ position: 'fixed', inset: 0, zIndex: 40 }} onClick={() => setMenuOpen(false)} />
              <div style={{ position: 'absolute', right: 0, top: '100%', marginTop: '4px', width: '170px', backgroundColor: 'var(--surface)', borderRadius: '10px', border: '1px solid var(--border)', boxShadow: '0 8px 24px rgba(0,0,0,0.1)', zIndex: 50, padding: '0.3rem', overflow: 'hidden' }}>
                <MenuItem icon="eye"      label="Preview"  onClick={() => { setMenuOpen(false); onView(doc) }} />
                {canDownload && <MenuItem icon="download"  label="Download" onClick={() => { setMenuOpen(false); handleDownload() }} />}
                {canUpdate && doc.status === 'active'   && <MenuItem icon="archive"  label="Archive"  onClick={handleArchive} />}
                {isAdmin    && doc.status !== 'active'  && <MenuItem icon="restore"  label="Restore"  onClick={handleRestore} />}
                {canDelete  && (
                  <>
                    <div style={{ height: '1px', backgroundColor: 'var(--bg)', margin: '0.2rem 0' }} />
                    <MenuItem icon="trash" label="Delete" onClick={handleDelete} danger />
                  </>
                )}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Meta row */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '6px' }}>
        <div style={{ display: 'flex', align: 'center', gap: '8px' }}>
          <span style={{ fontSize: '0.7rem', fontWeight: 600, backgroundColor: 'var(--bg)', color: 'var(--text-secondary)', padding: '2px 7px', borderRadius: '999px', border: '1px solid var(--border)' }}>
            {doc.file_type.toUpperCase()}
          </span>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', lineHeight: '1.6rem' }}>
            {formatFileSize(doc.file_size)}
          </span>
        </div>
        <span style={{ fontSize: '0.7rem', fontWeight: 600, padding: '2px 7px', borderRadius: '999px', backgroundColor: statusStyle.bg, color: statusStyle.color }}>
          {statusStyle.label}
        </span>
      </div>

      {/* Footer — date */}
      <div style={{ borderTop: '1px solid var(--border)', paddingTop: '0.625rem' }}>
        <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', margin: 0 }}>
          {formatDateTime(doc.created_at)}
        </p>
      </div>
    </div>
  )
}

function MenuItem({ icon, label, onClick, danger }: { icon: string; label: string; onClick: () => void; danger?: boolean }) {
  const icons: Record<string, React.ReactNode> = {
    eye:      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>,
    download: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>,
    archive:  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="21 8 21 21 3 21 3 8"/><rect x="1" y="3" width="22" height="5"/><line x1="10" y1="12" x2="14" y2="12"/></svg>,
    restore:  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-4.5"/></svg>,
    trash:    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg>,
  }
  return (
    <button onClick={onClick} style={{ width: '100%', display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 8px', border: 'none', borderRadius: '7px', backgroundColor: 'transparent', cursor: 'pointer', fontSize: '0.83rem', fontWeight: 500, color: danger ? '#dc2626' : 'var(--text-secondary)', textAlign: 'left', fontFamily: 'inherit' }}>
      {icons[icon]}{label}
    </button>
  )
}
