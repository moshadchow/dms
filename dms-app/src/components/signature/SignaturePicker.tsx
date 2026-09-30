import { useEffect, useRef, useState } from 'react'
import { workflowApi } from '@/api/workflow.api'
import type { Signature } from '@/types/workflow.types'

interface SignaturePickerProps {
  /** Selected signature id; null when nothing is chosen yet. */
  value: number | null
  onChange: (id: number | null) => void
}

/**
 * Signature selector for submit/approval dialogs.
 *
 * Loads the current user's signatures and pre-selects the newest so the
 * payload carries an explicit `signature_id`. The final PDF falls back to the
 * user's active signature when no id is sent, so an empty state is not an error.
 */
export default function SignaturePicker({ value, onChange }: SignaturePickerProps) {
  const [signatures, setSignatures] = useState<Signature[]>([])
  const [loading, setLoading] = useState(true)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [previewId, setPreviewId] = useState<number | null>(null)
  const previewUrlRef = useRef<string | null>(null)
  const valueRef = useRef<number | null>(value)
  const onChangeRef = useRef(onChange)

  useEffect(() => {
    valueRef.current = value
    onChangeRef.current = onChange
  }, [value, onChange])

  // Load once on mount (callers may pass an inline onChange, so it is held in a ref).
  useEffect(() => {
    let active = true
    workflowApi
      .listSignatures()
      .then((sigs) => {
        if (!active) return
        setSignatures(sigs)
        if (valueRef.current === null && sigs.length > 0) {
          onChangeRef.current(sigs[0].id)
        }
      })
      .catch(() => {
        if (active) setSignatures([])
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  // Keep the preview in sync with the selection. State is only set from the
  // async callback; a null/stale selection is simply not rendered.
  useEffect(() => {
    if (value === null) return
    let active = true
    workflowApi
      .getSignatureFileUrl(value)
      .then((url) => {
        if (!active) {
          URL.revokeObjectURL(url)
          return
        }
        if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current)
        previewUrlRef.current = url
        setPreviewId(value)
        setPreviewUrl(url)
      })
      .catch(() => {})
    return () => {
      active = false
    }
  }, [value])

  useEffect(() => {
    return () => {
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current)
    }
  }, [])

  if (loading) {
    return (
      <div>
        <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text)', marginBottom: 6 }}>
          Signature
        </label>
        <p style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)', margin: 0 }}>Loading signatures…</p>
      </div>
    )
  }

  if (signatures.length === 0) {
    return (
      <div>
        <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text)', marginBottom: 6 }}>
          Signature
        </label>
        <div style={{ padding: '0.75rem 1rem', border: '1px dashed var(--border)', borderRadius: 8, backgroundColor: 'var(--bg)', fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>
          No signature on file — ask an administrator to upload one. The final PDF will show no signature.
        </div>
      </div>
    )
  }

  return (
    <div>
      <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text)', marginBottom: 6 }}>
        Signature
      </label>
      <select
        className="input"
        value={value ?? ''}
        onChange={(e) => onChange(Number(e.target.value) || null)}
        style={{ width: '100%', marginBottom: 8 }}
      >
        {value === null && <option value="">Select signature</option>}
        {signatures.map((s) => (
          <option key={s.id} value={s.id}>
            {s.file_name} · {new Date(s.created_at).toLocaleDateString()}
          </option>
        ))}
      </select>
      {previewId === value && previewUrl && (
        <div style={{ padding: '0.5rem 0.75rem', border: '1px solid var(--border)', borderRadius: 8, backgroundColor: 'var(--bg)', textAlign: 'center' }}>
          <img
            src={previewUrl}
            alt="Selected signature preview"
            style={{ maxWidth: '100%', maxHeight: '60px', objectFit: 'contain' }}
          />
        </div>
      )}
    </div>
  )
}
