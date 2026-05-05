import { useState, useEffect } from 'react'
import { toast } from 'react-hot-toast'
import { documentsApi } from '@/api/documents.api'
import { getErrorMessage } from '@/api/client'
import { formatFileSize, formatDateTime } from '@/utils/formatters'
import { usePermissions } from '@/hooks/usePermissions'
import type { Document } from '@/types/document.types'

interface Props {
  doc:     Document | null
  onClose: () => void
}

export default function DocumentViewer({ doc, onClose }: Props) {
  const { canDownload } = usePermissions()
  const [blobUrl, setBlobUrl]       = useState<string | null>(null)
  const [loading, setLoading]       = useState(false)
  const [downloading, setDownloading] = useState(false)

  // Fetch the file as a blob so we can render it with the auth header
  useEffect(() => {
    if (!doc) { setBlobUrl(null); return }

    const token = localStorage.getItem('access_token')
    const base  = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'
    const url   = `${base}/api/v1/documents/${doc.id}/view`

    setLoading(true)
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => {
        if (!r.ok) throw new Error('Failed to load file')
        return r.blob()
      })
      .then((blob) => {
        const objectUrl = URL.createObjectURL(blob)
        setBlobUrl(objectUrl)
      })
      .catch(() => toast.error('Failed to load preview'))
      .finally(() => setLoading(false))

    return () => {
      setBlobUrl((prev) => { if (prev) URL.revokeObjectURL(prev); return null })
    }
  }, [doc?.id])

  const handleDownload = async () => {
    if (!doc) return
    setDownloading(true)
    try {
      await documentsApi.download(doc.id, doc.file_name)
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setDownloading(false)
    }
  }

  if (!doc) return null

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 60, display: 'flex', flexDirection: 'column' }}>
      {/* Backdrop */}
      <div style={{ position: 'absolute', inset: 0, backgroundColor: 'rgba(15,23,42,0.85)' }} onClick={onClose} />

      {/* Modal */}
      <div style={{ position: 'relative', margin: 'auto', width: 'calc(100vw - 2rem)', maxWidth: '900px', height: 'calc(100vh - 4rem)', backgroundColor: '#fff', borderRadius: '1rem', overflow: 'hidden', display: 'flex', flexDirection: 'column', boxShadow: '0 24px 80px rgba(0,0,0,0.4)' }}>

        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.875rem 1.25rem', borderBottom: '1px solid #f1f5f9', flexShrink: 0 }}>
          <div style={{ overflow: 'hidden', flex: 1 }}>
            <p style={{ fontWeight: 700, fontSize: '0.95rem', color: '#0f172a', margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {doc.title}
            </p>
            <p style={{ fontSize: '0.72rem', color: '#94a3b8', margin: '2px 0 0' }}>
              {doc.file_name} · {formatFileSize(doc.file_size)} · {formatDateTime(doc.created_at)}
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginLeft: '1rem', flexShrink: 0 }}>
            {canDownload && (
              <button
                onClick={handleDownload}
                disabled={downloading}
                style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 12px', backgroundColor: '#1e293b', color: '#fff', border: 'none', borderRadius: '8px', fontSize: '0.8rem', fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}
              >
                {downloading
                  ? <span style={{ width: '12px', height: '12px', border: '2px solid rgba(255,255,255,0.3)', borderTopColor: '#fff', borderRadius: '50%', animation: 'spin 0.7s linear infinite', display: 'inline-block' }} />
                  : <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                }
                Download
              </button>
            )}
            <button onClick={onClose} style={{ width: '32px', height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '8px', border: 'none', backgroundColor: '#f8fafc', cursor: 'pointer', color: '#475569' }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>
        </div>

        {/* Preview area */}
        <div style={{ flex: 1, overflow: 'hidden', backgroundColor: '#f8fafc', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {loading ? (
            <div style={{ textAlign: 'center' }}>
              <div style={{ width: '32px', height: '32px', border: '3px solid #e2e8f0', borderTopColor: '#4f46e5', borderRadius: '50%', animation: 'spin 0.7s linear infinite', margin: '0 auto 0.75rem' }} />
              <p style={{ color: '#94a3b8', fontSize: '0.875rem', margin: 0 }}>Loading preview…</p>
            </div>
          ) : blobUrl ? (
            doc.file_type === 'image' ? (
              <img
                src={blobUrl}
                alt={doc.title}
                style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain', borderRadius: '4px' }}
              />
            ) : doc.file_type === 'pdf' ? (
              <iframe
                src={blobUrl}
                style={{ width: '100%', height: '100%', border: 'none' }}
                title={doc.title}
              />
            ) : (
              /* Excel and other types — show download prompt */
              <div style={{ textAlign: 'center', padding: '2rem' }}>
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" strokeWidth="1.5" style={{ margin: '0 auto 1rem', display: 'block' }}>
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                  <polyline points="14 2 14 8 20 8"/>
                </svg>
                <p style={{ fontWeight: 600, color: '#64748b', margin: '0 0 0.5rem' }}>
                  Preview not available for {doc.file_type.toUpperCase()} files
                </p>
                {canDownload && (
                  <button
                    onClick={handleDownload}
                    style={{ padding: '8px 18px', backgroundColor: '#1e293b', color: '#fff', border: 'none', borderRadius: '8px', fontSize: '0.875rem', fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}
                  >
                    Download to view
                  </button>
                )}
              </div>
            )
          ) : (
            <p style={{ color: '#94a3b8' }}>Unable to load preview</p>
          )}
        </div>
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
