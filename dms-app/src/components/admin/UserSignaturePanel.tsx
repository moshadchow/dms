import { useState, useEffect, useRef, useCallback } from 'react'
import { toast } from 'react-hot-toast'
import { workflowApi } from '@/api/workflow.api'
import { getErrorMessage } from '@/api/client'
import ConfirmDialog from '@/components/ui/ConfirmDialog'
import type { Signature } from '@/types/workflow.types'

interface Props {
  userId: number
  userName: string
  isOpen: boolean
  onClose: () => void
}

const ALLOWED_MIME = ['image/jpeg', 'image/png']
const MAX_BYTES = 5 * 1024 * 1024

export default function UserSignaturePanel({ userId, userName, isOpen, onClose }: Props) {
  const [signature, setSignature] = useState<Signature | null>(null)
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const previewUrlRef = useRef<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const loadSignature = useCallback(async () => {
    setLoading(true)
    try {
      const sigs = await workflowApi.adminListSignaturesForUser(userId)
      const active = sigs.length > 0 ? sigs[0] : null
      setSignature(active)
      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current)
        previewUrlRef.current = null
      }
      if (active) {
        const url = await workflowApi.getSignatureFileUrl(active.id)
        previewUrlRef.current = url
        setPreviewUrl(url)
      } else {
        setPreviewUrl(null)
      }
    } catch {
      toast.error('Failed to load signature')
    } finally {
      setLoading(false)
    }
  }, [userId])

  useEffect(() => {
    if (!isOpen) return
    loadSignature()
    return () => {
      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current)
        previewUrlRef.current = null
      }
      setPreviewUrl(null)
      setSignature(null)
    }
  }, [isOpen, loadSignature])

  const validateFile = (file: File): string | null => {
    if (!ALLOWED_MIME.includes(file.type)) {
      return 'Only JPEG and PNG files are allowed'
    }
    if (file.size > MAX_BYTES) {
      return 'File size must be under 5 MB'
    }
    return null
  }

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    const error = validateFile(file)
    if (error) {
      toast.error(error)
      if (fileInputRef.current) fileInputRef.current.value = ''
      return
    }

    setUploading(true)
    try {
      const result = await workflowApi.adminUploadSignatureForUser(userId, file, 'e_signature')
      setSignature(result)
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current)
      const url = await workflowApi.getSignatureFileUrl(result.id)
      previewUrlRef.current = url
      setPreviewUrl(url)
      toast.success(signature ? 'Signature replaced' : 'Signature uploaded')
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleDelete = async () => {
    if (!signature) return
    setDeleting(true)
    try {
      await workflowApi.adminDeleteSignatureForUser(userId, signature.id)
      setSignature(null)
      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current)
        previewUrlRef.current = null
      }
      setPreviewUrl(null)
      setShowDeleteConfirm(false)
      toast.success('Signature deleted')
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setDeleting(false)
    }
  }

  if (!isOpen) return null

  return (
    <div role="dialog" aria-modal="true" aria-labelledby="sig-panel-title" style={{ position: 'fixed', inset: 0, zIndex: 60, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem' }}>
      <div style={{ position: 'absolute', inset: 0, backgroundColor: 'rgba(15,23,42,0.45)', backdropFilter: 'blur(2px)' }} onClick={onClose} />
      <div style={{ position: 'relative', width: '100%', maxWidth: '420px', backgroundColor: 'var(--surface)', borderRadius: '1rem', boxShadow: 'var(--shadow-lg)', padding: '1.5rem', border: '1px solid var(--border)' }}>

        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
          <div>
            <h3 id="sig-panel-title" style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text)', margin: 0 }}>
              Signature
            </h3>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)', margin: '2px 0 0' }}>
              {userName}
            </p>
          </div>
          <button onClick={onClose} style={{ width: '28px', height: '28px', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '6px', border: 'none', backgroundColor: 'var(--bg)', cursor: 'pointer', color: 'var(--text-secondary)' }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>

        {/* Content */}
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem' }}>
            <div style={{ width: '24px', height: '24px', border: '3px solid #e2e8f0', borderTopColor: '#4f46e5', borderRadius: '50%', animation: 'spin 0.7s linear infinite' }} />
            <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
          </div>
        ) : (
          <>
            {/* Signature preview */}
            {signature && previewUrl && (
              <div style={{ marginBottom: '1rem', padding: '1rem', backgroundColor: 'var(--bg)', borderRadius: '0.75rem', border: '1px solid var(--border)', textAlign: 'center' }}>
                <img
                  src={previewUrl}
                  alt="Signature preview"
                  style={{ maxWidth: '100%', maxHeight: '150px', objectFit: 'contain' }}
                />
                <p style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', margin: '0.5rem 0 0' }}>
                  {signature.file_name} &middot; {signature.sig_type === 'e_signature' ? 'E-Signature' : 'Wet Signature'}
                </p>
              </div>
            )}

            {/* No signature state */}
            {!signature && (
              <div style={{ marginBottom: '1rem', padding: '1.5rem', backgroundColor: 'var(--bg)', borderRadius: '0.75rem', border: '1px dashed var(--border)', textAlign: 'center' }}>
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="1.5" style={{ margin: '0 auto 0.5rem', display: 'block' }}>
                  <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/>
                </svg>
                <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', margin: 0 }}>
                  No signature on file
                </p>
              </div>
            )}

            {/* Actions */}
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <input
                ref={fileInputRef}
                type="file"
                accept=".jpg,.jpeg,.png"
                onChange={handleFileSelect}
                style={{ display: 'none' }}
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
                style={{
                  flex: 1, padding: '0.625rem', borderRadius: '0.5rem', border: 'none',
                  backgroundColor: 'var(--primary)', color: '#fff',
                  fontSize: '0.82rem', fontWeight: 600, cursor: uploading ? 'not-allowed' : 'pointer',
                  fontFamily: 'inherit', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px',
                  opacity: uploading ? 0.7 : 1,
                }}
              >
                {uploading ? (
                  <><span style={{ width: '14px', height: '14px', border: '2px solid rgba(255,255,255,0.3)', borderTopColor: '#fff', borderRadius: '50%', animation: 'spin 0.7s linear infinite', display: 'inline-block' }} />{signature ? 'Replacing…' : 'Uploading…'}</>
                ) : (
                  <><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>{signature ? 'Replace' : 'Upload'}</>
                )}
              </button>
              {signature && (
                <button
                  onClick={() => setShowDeleteConfirm(true)}
                  style={{
                    padding: '0.625rem 1rem', borderRadius: '0.5rem',
                    border: '1px solid var(--danger)', backgroundColor: 'transparent',
                    color: 'var(--danger)', fontSize: '0.82rem', fontWeight: 600,
                    cursor: 'pointer', fontFamily: 'inherit',
                  }}
                >
                  Delete
                </button>
              )}
            </div>
          </>
        )}
      </div>

      <ConfirmDialog
        isOpen={showDeleteConfirm}
        title="Delete signature"
        message={`Delete "${userName}"'s signature? This cannot be undone.`}
        confirmLabel="Delete"
        danger
        loading={deleting}
        onConfirm={handleDelete}
        onCancel={() => setShowDeleteConfirm(false)}
      />
    </div>
  )
}
