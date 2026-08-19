import { useState, useEffect, useRef } from 'react'
import { toast } from 'react-hot-toast'
import { workflowApi } from '@/api/workflow.api'
import type { Signature } from '@/types/workflow.types'
import Button from '@/components/ui/Button'
import SignatureUpload from '@/components/workflow/SignatureUpload'
import SignaturePad from '@/components/workflow/SignaturePad'

interface SignaturePickerProps {
  selectedSignatureId?: number | null
  onSelect: (signatureId: number | null) => void
  disabled?: boolean
  memoAuthorSignatureId?: number | null
}

export default function SignaturePicker({
  selectedSignatureId = null,
  onSelect,
  disabled = false,
  memoAuthorSignatureId,
}: SignaturePickerProps) {
  const [signatures, setSignatures] = useState<Signature[]>([])
  const [loading, setLoading] = useState(true)
  const [mode, setMode] = useState<'select' | 'upload' | 'draw'>('select')
  const blobUrlsRef = useRef<Record<number, string>>({})
  const [sigBlobUrls, setSigBlobUrls] = useState<Record<number, string>>({})

  const isMemoScoped = memoAuthorSignatureId !== undefined

  const fetchBlobUrls = async (sigs: Signature[]) => {
    const results = await Promise.allSettled(
      sigs.map(async (sig) => {
        if (!sig.file_path) return null
        try {
          const url = await workflowApi.getSignatureFileUrl(sig.id)
          return { id: sig.id, url }
        } catch {
          return null
        }
      })
    )
    const newUrls: Record<number, string> = {}
    for (const r of results) {
      if (r.status === 'fulfilled' && r.value) {
        newUrls[r.value.id] = r.value.url
        blobUrlsRef.current[r.value.id] = r.value.url
      }
    }
    setSigBlobUrls((prev) => ({ ...prev, ...newUrls }))
  }

  useEffect(() => {
    if (isMemoScoped) {
      if (memoAuthorSignatureId != null) {
        workflowApi.getSignatureFileUrl(memoAuthorSignatureId)
          .then((url) => {
            setSigBlobUrls({ [memoAuthorSignatureId]: url })
            blobUrlsRef.current[memoAuthorSignatureId] = url
          })
          .catch(() => {})
          .finally(() => setLoading(false))
      } else {
        setLoading(false)
      }
    } else {
      workflowApi.listSignatures().then((sigs) => {
        setSignatures(sigs)
        fetchBlobUrls(sigs)
      }).finally(() => setLoading(false))
    }

    return () => {
      Object.values(blobUrlsRef.current).forEach(URL.revokeObjectURL)
      blobUrlsRef.current = {}
    }
  }, [isMemoScoped, memoAuthorSignatureId])

  const handleUpload = async (file: File) => {
    try {
      const sig = await workflowApi.uploadSignature(file, 'e_signature')
      if (isMemoScoped) {
        if (sig.file_path) {
          const url = await workflowApi.getSignatureFileUrl(sig.id)
          setSigBlobUrls({ [sig.id]: url })
          blobUrlsRef.current = { [sig.id]: url }
        }
      } else {
        setSignatures((prev) => [...prev, sig])
        if (sig.file_path) {
          const url = await workflowApi.getSignatureFileUrl(sig.id)
          setSigBlobUrls((prev) => ({ ...prev, [sig.id]: url }))
          blobUrlsRef.current[sig.id] = url
        }
      }
      onSelect(sig.id)
      setMode('select')
      toast.success('Signature uploaded')
    } catch {
      toast.error('Failed to upload signature')
    }
  }

  const handleDrawBlob = async (blob: Blob) => {
    const file = new File([blob], 'signature.png', { type: 'image/png' })
    try {
      const sig = await workflowApi.uploadSignature(file, 'wet_signature')
      if (isMemoScoped) {
        if (sig.file_path) {
          const url = await workflowApi.getSignatureFileUrl(sig.id)
          setSigBlobUrls({ [sig.id]: url })
          blobUrlsRef.current = { [sig.id]: url }
        }
      } else {
        setSignatures((prev) => [...prev, sig])
        if (sig.file_path) {
          const url = await workflowApi.getSignatureFileUrl(sig.id)
          setSigBlobUrls((prev) => ({ ...prev, [sig.id]: url }))
          blobUrlsRef.current[sig.id] = url
        }
      }
      onSelect(sig.id)
      setMode('select')
      toast.success('Signature saved')
    } catch {
      toast.error('Failed to save signature')
    }
  }

  if (disabled) {
    const current = signatures.find((s) => s.id === selectedSignatureId)
    return (
      <div style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: '1rem' }}>
        <p style={{ fontSize: '0.85rem', color: '#64748b', marginBottom: '0.5rem' }}>Attached Signature</p>
        {current ? (
          sigBlobUrls[current.id] ? (
            <img
              src={sigBlobUrls[current.id]}
              alt="Signature"
              style={{ maxWidth: 300, maxHeight: 150, border: '1px solid #e2e8f0', borderRadius: 6 }}
            />
          ) : (
            <p style={{ fontSize: '0.85rem', color: '#94a3b8' }}>Loading…</p>
          )
        ) : (
          <p style={{ fontSize: '0.85rem', color: '#94a3b8' }}>No signature attached</p>
        )}
      </div>
    )
  }

  if (isMemoScoped) {
    return (
      <div style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: '1rem' }}>
        {mode === 'select' && (
          <>
            <p style={{ fontSize: '0.85rem', color: '#334155', marginBottom: '0.75rem' }}>Select or add a signature</p>
            {loading ? (
              <div style={{ textAlign: 'center', color: '#94a3b8', fontSize: '0.8rem', padding: '1rem' }}>Loading signature...</div>
            ) : selectedSignatureId && sigBlobUrls[selectedSignatureId] ? (
              <div style={{ marginBottom: '1rem' }}>
                <div style={{ fontWeight: 600, fontSize: '0.8rem', marginBottom: '0.25rem' }}>Attached Signature</div>
                <img
                  src={sigBlobUrls[selectedSignatureId]}
                  alt="Signature"
                  style={{ maxWidth: 300, maxHeight: 150, border: '1px solid #e2e8f0', borderRadius: 6 }}
                />
              </div>
            ) : (
              <p style={{ fontSize: '0.85rem', color: '#94a3b8', marginBottom: '1rem' }}>No signature attached</p>
            )}
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              <Button variant="secondary" size="sm" onClick={() => setMode('upload')}>
                Upload E-Signature
              </Button>
              <Button variant="secondary" size="sm" onClick={() => setMode('draw')}>
                Draw Wet Signature
              </Button>
              {selectedSignatureId && (
                <Button variant="ghost" size="sm" onClick={() => onSelect(null)}>Remove</Button>
              )}
            </div>
          </>
        )}

        {mode === 'upload' && (
          <SignatureUpload onFileSelected={handleUpload} onCancel={() => setMode('select')} />
        )}

        {mode === 'draw' && (
          <SignaturePad onCapture={handleDrawBlob} onCancel={() => setMode('select')} />
        )}
      </div>
    )
  }

  return (
    <div style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: '1rem' }}>
      {mode === 'select' && (
        <>
          <p style={{ fontSize: '0.85rem', color: '#334155', marginBottom: '0.75rem' }}>Select or add a signature</p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: '0.75rem', marginBottom: '1rem' }}>
            {loading && (
              <div style={{ gridColumn: '1 / -1', textAlign: 'center', color: '#94a3b8', fontSize: '0.8rem', padding: '1rem' }}>Loading signatures...</div>
            )}
            {!loading && signatures.map((sig) => (
              <button
                key={sig.id}
                type="button"
                onClick={() => onSelect(sig.id)}
                style={{
                  border: sig.id === selectedSignatureId ? '2px solid #4f46e5' : '1px solid #e2e8f0',
                  borderRadius: 8,
                  padding: '0.5rem',
                  background: sig.id === selectedSignatureId ? '#eef2ff' : 'white',
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
              >
                <div style={{ fontWeight: 600, fontSize: '0.8rem', marginBottom: '0.25rem' }}>
                  {sig.sig_type === 'e_signature' ? '📝 E-Signature' : '✍️ Wet Signature'}
                </div>
                {sigBlobUrls[sig.id] ? (
                  <img
                    src={sigBlobUrls[sig.id]}
                    alt=""
                    style={{ maxWidth: '100%', height: 60, objectFit: 'contain', border: '1px solid #e2e8f0', borderRadius: 4 }}
                  />
                ) : (
                  <div style={{ width: '100%', height: 60, border: '1px dashed #cbd5e1', borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#94a3b8', fontSize: '0.7rem' }}>
                    {loading ? 'Loading…' : 'No preview'}
                  </div>
                )}
              </button>
            ))}
            {!loading && signatures.length === 0 && (
              <div style={{ gridColumn: '1 / -1', textAlign: 'center', color: '#94a3b8', fontSize: '0.8rem', padding: '1rem' }}>No signatures saved yet</div>
            )}
          </div>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <Button variant="secondary" size="sm" onClick={() => setMode('upload')}>
              Upload E-Signature
            </Button>
            <Button variant="secondary" size="sm" onClick={() => setMode('draw')}>
              Draw Wet Signature
            </Button>
            {selectedSignatureId && (
              <Button variant="ghost" size="sm" onClick={() => {
                setSignatures((prev) => prev.filter((s) => s.id !== selectedSignatureId))
                onSelect(null)
              }}>Remove</Button>
            )}
          </div>
        </>
      )}

      {mode === 'upload' && (
        <SignatureUpload onFileSelected={handleUpload} onCancel={() => setMode('select')} />
      )}

      {mode === 'draw' && (
        <SignaturePad onCapture={handleDrawBlob} onCancel={() => setMode('select')} />
      )}
    </div>
  )
}
